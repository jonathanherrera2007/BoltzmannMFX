//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <bmx.H>
#include <bmx_chem.H>
#include <bmx_chem_K.H>
#include <bmx_des_K.H>
#include <bmx_chem_species_parms.H>
#include <bmx_fluid_parms.H>
#include <bmx_pc_phosphorus.H>

#include <cstdint>
#include <unordered_map>
#include <vector>

/**
 * @brief this function splits particles if some criterion is met
 * @param time current time at which split occurs
 */
void
BMXParticleContainer::split_particles (Real /*time*/)
{
  Real l_max_vol  = SPECIES::max_vol; 
  Real l_max_len  = SPECIES::max_len; 
  Real l_max_rad  = SPECIES::max_rad; 
  Real l_brnch_prob = SPECIES::brnch_prob;
  Real l_split_prob = SPECIES::split_prob;
  Real l_overlap  = BMXChemistry::p_overlap;
  int l_num_reals = BMXChemistry::p_num_reals;
  int l_num_ints  = BMXChemistry::p_num_ints;
  const bool p10_enabled =
      BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) ==
      BMXChemLayout::MeshMode::enabled;

  auto stable_key = [] (int id, int cpu) -> std::uint64_t {
    return (static_cast<std::uint64_t>(
                static_cast<std::uint32_t>(cpu)) << 32) |
           static_cast<std::uint32_t>(id);
  };
  std::unordered_map<std::uint64_t,unsigned int> frozen_split_decisions;

  // Enabled mode freezes the complete MPI-local candidate set before any
  // particle or bond is mutated. The global preflight then rejects shared
  // particles/bonds atomically; the execution pass below reuses these exact
  // decisions and therefore consumes no outcome-dependent second RNG draw.
  if (p10_enabled) {
    BMXPhosphorus::validateBondTopology(*this);
    std::vector<BMXPhosphorus::TopologyEventParticipants> local_events;
    for (int lev = 0; lev <= finest_level; ++lev) {
      for (BMXParIter pti(*this, lev); pti.isValid(); ++pti) {
        auto& particles = pti.GetArrayOfStructs();
        auto* pstruct = particles().dataPtr();
        const int count = particles.size();
        Gpu::DeviceVector<unsigned int> decisions(count, 0);
        auto* decisions_ptr = decisions.data();
        amrex::ParallelForRNG(count,
            [=] AMREX_GPU_DEVICE (
                int index, amrex::RandomEngine const& engine) noexcept
            {
              int new_particles = 0;
              auto& particle = pstruct[index];
              if (checkSplit(&particle.rdata(0), &particle.idata(0),
                    l_max_vol, l_max_len, l_max_rad, l_brnch_prob,
                    l_split_prob, &new_particles, engine)) {
                decisions_ptr[index] = new_particles;
              }
            });
        amrex::Gpu::streamSynchronize();

        amrex::Gpu::HostVector<unsigned int> host_decisions(count);
        amrex::Gpu::HostVector<ParticleType> host_particles(count);
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         decisions.begin(), decisions.end(),
                         host_decisions.begin());
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         particles.begin(), particles.begin() + count,
                         host_particles.begin());
        for (int index = 0; index < count; ++index) {
          if (host_decisions[index] == 0) continue;
          const auto& particle = host_particles[index];
          const int id = particle.idata(intIdx::id);
          const int cpu = particle.idata(intIdx::cpu);
          if (!frozen_split_decisions.emplace(
                  stable_key(id, cpu), host_decisions[index]).second) {
            amrex::Abort("P10_ABORT_SIMULTANEOUS_TOPOLOGY_CONFLICT");
          }
          local_events.push_back({0, id, cpu, -1, -1});
        }
      }
    }
    BMXPhosphorus::requireDisjointTopologyBatch(*this, local_events);
  }

  for (int lev = 0; lev <= finest_level; lev++) {

      for (BMXParIter pti(*this, lev); pti.isValid(); ++pti)
      {
        auto& particles = pti.GetArrayOfStructs();
        BMXParticleContainer::ParticleType* pstruct = particles().dataPtr();

        const int grid = pti.index();
        const int tile = pti.LocalTileIndex();
        auto& particle_tile = this->GetParticles(lev)[std::make_pair(grid,tile)];

        const int np = particles.size();

        // whether each particle will be split
        Gpu::DeviceVector<unsigned int> do_split(np+1, 0);
        auto do_split_p = do_split.data();
        if (p10_enabled) {
          amrex::Gpu::HostVector<ParticleType> host_particles(np);
          amrex::Gpu::HostVector<unsigned int> host_decisions(np+1, 0);
          amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                           particles.begin(), particles.begin() + np,
                           host_particles.begin());
          for (int index = 0; index < np; ++index) {
            const auto& particle = host_particles[index];
            const auto decision = frozen_split_decisions.find(stable_key(
                particle.idata(intIdx::id), particle.idata(intIdx::cpu)));
            if (decision != frozen_split_decisions.end()) {
              host_decisions[index] = decision->second;
            }
          }
          amrex::Gpu::copy(amrex::Gpu::hostToDevice,
                           host_decisions.begin(), host_decisions.end(),
                           do_split.begin());
        } else {
          amrex::ParallelForRNG( np, [=] AMREX_GPU_DEVICE (int i,
                amrex::RandomEngine const& engine) noexcept
          {
              int n_new;
              BMXParticleContainer::ParticleType& p = pstruct[i];
              if (checkSplit(&p.rdata(0), &p.idata(0), l_max_vol,
                    l_max_len, l_max_rad, l_brnch_prob, l_split_prob,
                    &n_new, engine))
              {
                  do_split_p[i] = n_new;
              }
          });
        }
        Gpu::Device::synchronize();

        // Prefix sum to count total number of new particles to create
        Gpu::DeviceVector<unsigned int> offsets(np+1);
        Gpu::exclusive_scan(do_split.begin(), do_split.end(), offsets.begin());
        unsigned int num_split;
#ifdef AMREX_USE_GPU
        Gpu::dtoh_memcpy(&num_split,offsets.dataPtr()+np,sizeof(unsigned int));
#else
        std::memcpy(&num_split,offsets.dataPtr()+np,sizeof(unsigned int));
#endif

        // make room for new particles - invalidates iterators, so get the ptr again
        particle_tile.resize(np+num_split);
        particle_tile.setNumNeighbors(0);
        pstruct = particles().dataPtr();

        // Update NextID to include particles created in this function
        Long next_pid;
#ifdef AMREX_USE_OMP
#pragma omp critical (add_plasma_nextid)
#endif
        {
            next_pid = ParticleType::NextID();
            ParticleType::NextID(next_pid+num_split);
        }
        Real split_len = SPECIES::split_len;

        // Fill new particle data. If particle pid is split, the new particle
        // is at index np + poffsets[pid];
        auto poffsets = offsets.data();
        int my_proc = amrex::ParallelDescriptor::MyProc();
        amrex::ParallelForRNG( np, [=] AMREX_GPU_DEVICE (int pid, amrex::RandomEngine const& engine) noexcept
        {
            BMXParticleContainer::ParticleType& p_orig = pstruct[pid];

            // Check to see if particle satisfies some criteria for splitting
            // into two new particles
            // Real* p_par =  &p_orig.rdata(0);
            if (do_split_p[pid] == 1)
            {
                // std::printf("MAKING NEW PARTICLE FROM VOL = %f \n", p_par[realIdx::vol]);
                ParticleType& p = pstruct[np+poffsets[pid]];
                p.id()  = next_pid + poffsets[pid];
                p.cpu() = my_proc;

                Real *pos_orig = &p_orig.pos(0);
                Real *pos_new  = &p.pos(0);

                Real *par_orig = &p_orig.rdata(0);
                Real *par_new  = &p.rdata(0);

                int *ipar_orig = &p_orig.idata(0);
                int *ipar_new  = &p.idata(0);

                BMXPhosphorus::ParticleAmounts phosphorus_before;
                if (p10_enabled &&
                    BMXPhosphorus::captureParticleAmounts(
                        par_orig, phosphorus_before) !=
                        BMXPhosphorus::AmountStatus::ok) {
                  amrex::Abort("P10 split encountered invalid D/E/F amount state");
                }

                // Set parameters on new particle base on values from
                // original particle
                if (ipar_orig[intIdx::cell_type] == cellType::YEAST) {
                  setNewCell(pos_orig, pos_new, par_orig,
                             par_new, ipar_orig, ipar_new,
                             l_overlap, l_num_reals, l_num_ints, engine);
                } else {
                  setNewSegment(pos_orig, pos_new, par_orig,
                                par_new, ipar_orig, ipar_new,
                                l_num_reals, l_num_ints, split_len,
                                p.id(), p.cpu(), engine);
                }
                if (p10_enabled &&
                    BMXPhosphorus::partitionTwo(
                        phosphorus_before, par_orig, par_new) !=
                        BMXPhosphorus::AmountStatus::ok) {
                  amrex::Abort("P10 split produced invalid D/E/F owning volumes");
                }
                ipar_new[intIdx::id] = p.id();
                ipar_new[intIdx::cpu] = p.cpu();
                // printf("NEW segment id: %d cpu: %d site1: %d id1: %d cpu1: %d\n",
                //     ipar_new[intIdx::id],ipar_new[intIdx::cpu],ipar_new[intIdx::site1],
                //     ipar_new[intIdx::seg1_id1],ipar_new[intIdx::seg1_id2]);

                //                std::printf("OLD VOLUME OUT = %f \n", par_orig[realIdx::vol]);
                //                std::printf("NEW VOLUME OUT = %f \n", par_new[realIdx::vol]);
            } else if (do_split_p[pid] == 2) {

                ParticleType& p1 = pstruct[np+poffsets[pid]];
                p1.id()  = next_pid + poffsets[pid];
                p1.cpu() = my_proc;

                ParticleType& p2 = pstruct[np+poffsets[pid]+1];
                p2.id()  = next_pid + poffsets[pid]+1;
                p2.cpu() = my_proc;

                Real *pos_orig = &p_orig.pos(0);
                Real *pos_new1  = &p1.pos(0);
                Real *pos_new2  = &p2.pos(0);

                Real *par_orig = &p_orig.rdata(0);
                Real *par_new1  = &p1.rdata(0);
                Real *par_new2  = &p2.rdata(0);

                int *ipar_orig = &p_orig.idata(0);
                int *ipar_new1  = &p1.idata(0);
                int *ipar_new2  = &p2.idata(0);

                BMXPhosphorus::ParticleAmounts phosphorus_before;
                if (p10_enabled &&
                    BMXPhosphorus::captureParticleAmounts(
                        par_orig, phosphorus_before) !=
                        BMXPhosphorus::AmountStatus::ok) {
                  amrex::Abort("P10 branch split encountered invalid D/E/F amount state");
                }

                setNewSegments(pos_orig, pos_new1, pos_new2,
                               par_orig, par_new1, par_new2,
                               ipar_orig, ipar_new1, ipar_new2,
                               l_num_reals, l_num_ints, split_len,
                               p1.id(), p1.cpu(), p2.id(), p2.cpu(), engine);
                if (p10_enabled &&
                    BMXPhosphorus::partitionThree(
                        phosphorus_before, par_orig, par_new1, par_new2) !=
                        BMXPhosphorus::AmountStatus::ok) {
                  amrex::Abort("P10 branch split produced invalid D/E/F owning volumes");
                }

            } // if test
        }); // pid
      } // pti
  } // lev

  if (p10_enabled) {
    BMXPhosphorus::validateBondTopology(*this);
  }

  // Redistribute the particles so the new particles end up on the right processor
  Redistribute();
}
