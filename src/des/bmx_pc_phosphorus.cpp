//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <bmx_pc_phosphorus.H>

#include <bmx_pc.H>
#include <bmx_fluid_parms.H>

#include <AMReX_ParmParse.H>
#include <AMReX_VectorIO.H>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace
{
  BMXPhosphorus::CumulativeLedger ledger_state{};

  std::uint64_t particleKey (int id, int cpu)
  {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(cpu)) << 32) |
           static_cast<std::uint32_t>(id);
  }
}

namespace BMXPhosphorus
{
  ParticleTotals computeInternalAmounts (const BMXParticleContainer& particles)
  {
    ParticleTotals totals;
    totals.d = particles.computeParticleContent(
        realIdx::first_data + BMXChemLayout::P_D);
    totals.e = particles.computeParticleContent(
        realIdx::first_data + BMXChemLayout::P_E);
    totals.f = particles.computeParticleContent(
        realIdx::first_data + BMXChemLayout::P_F);
    return totals;
  }

  ParticleTotals computeTransferAmounts (const BMXParticleContainer& particles)
  {
    const int transfer_base = realIdx::first_data +
                              2 * NUM_PARTICLE_CHEM_COMPONENTS;
    ParticleTotals totals;
    totals.d = amrex::ReduceSum(particles,
        [=] AMREX_GPU_HOST_DEVICE (const BMXParticleContainer::ParticleType& p)
        {
          return p.rdata(transfer_base + BMXChemLayout::P_D);
        });
    totals.e = amrex::ReduceSum(particles,
        [=] AMREX_GPU_HOST_DEVICE (const BMXParticleContainer::ParticleType& p)
        {
          return p.rdata(transfer_base + BMXChemLayout::P_E);
        });
    totals.f = amrex::ReduceSum(particles,
        [=] AMREX_GPU_HOST_DEVICE (const BMXParticleContainer::ParticleType& p)
        {
          return p.rdata(transfer_base + BMXChemLayout::P_F);
        });
    amrex::ParallelDescriptor::ReduceRealSum(totals.d);
    amrex::ParallelDescriptor::ReduceRealSum(totals.e);
    amrex::ParallelDescriptor::ReduceRealSum(totals.f);
    return totals;
  }

  void requireAuditBuffersEmpty (const BMXParticleContainer& particles,
                                 const char* boundary)
  {
    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) return;

    const int working_base = realIdx::first_data +
                             NUM_PARTICLE_CHEM_COMPONENTS;
    const int increment_base = realIdx::first_data +
                               2 * NUM_PARTICLE_CHEM_COMPONENTS;
    auto working_l1 = [&particles, working_base] (int component)
    {
      amrex::Real result = amrex::ReduceSum(
          particles,
          [=] AMREX_GPU_HOST_DEVICE (
              const BMXParticleContainer::ParticleType& particle)
          {
            const amrex::Real amount = concentrationToAmount(
                particle.rdata(working_base + component),
                particle.rdata(realIdx::vol));
            return amrex::Math::abs(amount);
          });
      amrex::ParallelDescriptor::ReduceRealSum(result);
      return result;
    };
    auto increment_l1 = [&particles, increment_base] (int component)
    {
      amrex::Real result = amrex::ReduceSum(
          particles,
          [=] AMREX_GPU_HOST_DEVICE (
              const BMXParticleContainer::ParticleType& particle)
          {
            return amrex::Math::abs(
                particle.rdata(increment_base + component));
          });
      amrex::ParallelDescriptor::ReduceRealSum(result);
      return result;
    };

    const ParticleTotals working{
        working_l1(BMXChemLayout::P_D),
        working_l1(BMXChemLayout::P_E),
        working_l1(BMXChemLayout::P_F)};
    const ParticleTotals increment{
        increment_l1(BMXChemLayout::P_D),
        increment_l1(BMXChemLayout::P_E),
        increment_l1(BMXChemLayout::P_F)};
    if (!finite(working.d) || !finite(working.e) || !finite(working.f) ||
        !finite(increment.d) || !finite(increment.e) || !finite(increment.f) ||
        working.d != 0.0 || working.e != 0.0 || working.f != 0.0 ||
        increment.d != 0.0 || increment.e != 0.0 || increment.f != 0.0) {
      std::ostringstream message;
      message.precision(17);
      message << "P10 audit boundary " << boundary
              << " contains unaccounted working/increment phosphorus:"
              << " working_l1_D=" << working.d
              << " working_l1_E=" << working.e
              << " working_l1_F=" << working.f
              << " increment_l1_D=" << increment.d
              << " increment_l1_E=" << increment.e
              << " increment_l1_F=" << increment.f;
      amrex::Abort(message.str());
    }
  }

  void requireCheckpointParticlesSafe (
      BMXParticleContainer& particles,
      const std::string& checkpoint_directory,
      const std::string& particle_name)
  {
    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) return;

    auto reject = [](const std::string& reason)
    {
      amrex::Abort(
          "P09 checkpoint rejected before particle deserialization: " +
          reason);
    };

    std::string particle_directory = checkpoint_directory;
    if (!particle_directory.empty() &&
        particle_directory.back() != '/' &&
        particle_directory.back() != '\\') {
      particle_directory += '/';
    }
    particle_directory += particle_name;

    std::ifstream header(particle_directory + "/Header");
    if (!header.good()) reject("missing particle Header");

    std::string version;
    int dimension = 0;
    int real_components = 0;
    int int_components = 0;
    if (!(header >> version >> dimension >> real_components)) {
      reject("malformed particle Header prefix");
    }
    const std::string expected_version =
        sizeof(BMXParticleContainer::ParticleType::RealType) == 4
            ? "Version_Two_Dot_One_single"
            : "Version_Two_Dot_One_double";
    if (version != expected_version) {
      reject("particle checkpoint version/precision mismatch");
    }
    if (dimension != AMREX_SPACEDIM ||
        real_components != BMXParticleContainer::NStructReal +
                           particles.NumRealComps()) {
      reject("particle dimension or real-component count mismatch");
    }
    std::string component_name;
    for (int component = 0; component < real_components; ++component) {
      if (!(header >> component_name)) {
        reject("truncated particle real-component names");
      }
    }
    if (!(header >> int_components) ||
        int_components != BMXParticleContainer::NStructInt +
                          particles.NumIntComps()) {
      reject("particle integer-component count mismatch");
    }
    for (int component = 0; component < int_components; ++component) {
      if (!(header >> component_name)) {
        reject("truncated particle integer-component names");
      }
    }

    int is_checkpoint = 0;
    amrex::Long particle_count = 0;
    amrex::Long max_next_id = 0;
    int finest_level = -1;
    if (!(header >> is_checkpoint >> particle_count >> max_next_id >>
          finest_level) ||
        is_checkpoint != 1 || particle_count < 0 || max_next_id <= 0 ||
        finest_level < 0 || finest_level > particles.finestLevel()) {
      reject("malformed particle checkpoint controls");
    }

    struct GridRecord
    {
      int level = -1;
      int file_number = -1;
      int count = -1;
      amrex::Long offset = -1;
    };
    std::vector<int> grid_counts(static_cast<std::size_t>(finest_level) + 1);
    for (int level = 0; level <= finest_level; ++level) {
      if (!(header >> grid_counts[level]) || grid_counts[level] <= 0) {
        reject("malformed particle grid count");
      }
    }
    std::vector<GridRecord> records;
    amrex::Long counted_particles = 0;
    for (int level = 0; level <= finest_level; ++level) {
      for (int grid = 0; grid < grid_counts[level]; ++grid) {
        GridRecord record;
        record.level = level;
        if (!(header >> record.file_number >> record.count >> record.offset) ||
            record.file_number < 0 || record.count < 0 || record.offset < 0) {
          reject("malformed particle grid record");
        }
        if (counted_particles >
            std::numeric_limits<amrex::Long>::max() - record.count) {
          reject("particle count overflow");
        }
        counted_particles += record.count;
        records.push_back(record);
      }
    }
    header >> std::ws;
    if (!header.eof() || counted_particles != particle_count) {
      reject("particle Header count or trailing-data mismatch");
    }

    int data_digits = 5;
    amrex::ParmParse particle_parameters("particles");
    particle_parameters.queryAdd("datadigits_read", data_digits);
    if (data_digits <= 0) reject("invalid particles.datadigits_read");

    const auto problem_low = particles.Geom(0).ProbLoArray();
    const auto problem_high = particles.Geom(0).ProbHiArray();
    const int integer_chunk = 2 + int_components;
    const int real_chunk = AMREX_SPACEDIM + real_components;
    constexpr int particle_batch_size = 4096;
    int violation = 0;

    for (std::size_t record_index = 0;
         record_index < records.size(); ++record_index) {
      if (record_index % static_cast<std::size_t>(
              amrex::ParallelDescriptor::NProcs()) !=
          static_cast<std::size_t>(amrex::ParallelDescriptor::MyProc())) {
        continue;
      }
      const auto& record = records[record_index];
      if (record.count == 0) continue;

      std::string data_path = particle_directory + "/Level_" +
          amrex::Concatenate("", record.level, 1) + "/" +
          particles.DataPrefix() +
          amrex::Concatenate("", record.file_number, data_digits);
      std::ifstream data(data_path, std::ios::in | std::ios::binary);
      if (!data.good()) reject("missing particle data file " + data_path);
      data.seekg(static_cast<std::streamoff>(record.offset), std::ios::beg);
      if (!data.good()) reject("invalid particle data offset");

      int remaining = record.count;
      while (remaining > 0) {
        const int batch = std::min(remaining, particle_batch_size);
        std::vector<int> integers(
            static_cast<std::size_t>(batch) * integer_chunk);
        amrex::readIntData(integers.data(), integers.size(), data,
                           amrex::FPC::NativeIntDescriptor());
        if (!data.good()) reject("truncated particle integer data");
        for (int particle = 0; particle < batch; ++particle) {
          const std::size_t base =
              static_cast<std::size_t>(particle) * integer_chunk;
          const auto high = static_cast<std::uint32_t>(integers[base]);
          const auto low = static_cast<std::uint32_t>(integers[base + 1]);
          const std::uint64_t packed =
              (static_cast<std::uint64_t>(high) << 32) | low;
          const bool positive = (packed >> 63) != 0;
          const bool nonzero = ((packed >> 24) & 0x7FFFFFFFFFULL) != 0;
          if (!positive || !nonzero) violation = 2;
        }
        remaining -= batch;
      }

      remaining = record.count;
      while (remaining > 0) {
        const int batch = std::min(remaining, particle_batch_size);
        std::vector<BMXParticleContainer::ParticleType::RealType> reals(
            static_cast<std::size_t>(batch) * real_chunk);
        particles.ReadParticleRealData(reals.data(), reals.size(), data);
        if (!data.good()) reject("truncated particle real data");
        for (int particle = 0; particle < batch; ++particle) {
          const std::size_t base =
              static_cast<std::size_t>(particle) * real_chunk;
          for (int direction = 0; direction < AMREX_SPACEDIM; ++direction) {
            const amrex::Real position = reals[base + direction];
            if (!finite(position) ||
                (!particles.Geom(0).isPeriodic(direction) &&
                 (position < problem_low[direction] ||
                  position >= problem_high[direction]))) {
              violation = amrex::max(violation, 1);
            }
          }
        }
        remaining -= batch;
      }
    }

    amrex::ParallelDescriptor::ReduceIntMax(violation);
    if (violation == 2) {
      amrex::Abort(topologyReasonCode(
          TopologyReason::unmapped_particle_deletion));
    }
    if (violation == 1) {
      amrex::Abort(topologyReasonCode(
          TopologyReason::out_of_domain_particle));
    }
  }

  void requireRedistributionSafe (const BMXParticleContainer& particles)
  {
    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) return;

    const auto plo = particles.Geom(0).ProbLoArray();
    const auto phi = particles.Geom(0).ProbHiArray();
    const amrex::GpuArray<int,AMREX_SPACEDIM> periodic = {
        AMREX_D_DECL(particles.Geom(0).isPeriodic(0),
                     particles.Geom(0).isPeriodic(1),
                     particles.Geom(0).isPeriodic(2))};

    // ParticleReduce/ReduceMax deliberately skips invalid particles. This
    // guard must observe them before Redistribute compacts them, so reduce the
    // raw real-particle AoS for every tile instead of the filtered container.
    int violation = 0;
    for (int lev = 0; lev <= particles.finestLevel(); ++lev) {
      const auto& level_particles = particles.GetParticles(lev);
      for (const auto& entry : level_particles) {
        const auto& tile = entry.second;
        const int count = tile.numRealParticles();
        if (count == 0) continue;
        const auto& aos = tile.GetArrayOfStructs();
        const auto* pstruct = aos().dataPtr();
        amrex::ReduceOps<amrex::ReduceOpMax> reduce_op;
        amrex::ReduceData<int> reduce_data(reduce_op);
        using ReduceTuple = typename decltype(reduce_data)::Type;
        reduce_op.eval(
            count, reduce_data,
            [=] AMREX_GPU_DEVICE (int index) noexcept -> ReduceTuple
            {
              const auto& particle = pstruct[index];
              if (particle.id() <= 0) return {2};
              for (int dir = 0; dir < AMREX_SPACEDIM; ++dir) {
                const amrex::Real position = particle.pos(dir);
                if (!finite(position) ||
                    (!periodic[dir] &&
                     (position < plo[dir] || position >= phi[dir]))) {
                  return {1};
                }
              }
              return {0};
            });
        const auto tile_result = reduce_data.value(reduce_op);
        violation = amrex::max(violation, amrex::get<0>(tile_result));
      }
    }
    amrex::ParallelDescriptor::ReduceIntMax(violation);
    if (violation == 2) {
      amrex::Abort(topologyReasonCode(
          TopologyReason::unmapped_particle_deletion));
    }
    if (violation == 1) {
      amrex::Abort(topologyReasonCode(
          TopologyReason::out_of_domain_particle));
    }
  }

  void requireDisjointTopologyBatch (
      const BMXParticleContainer& particles,
      const std::vector<TopologyEventParticipants>& local_events)
  {
    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) return;

    std::vector<TopologyEventParticipants> all_events;
#ifdef AMREX_USE_MPI
    const int local_bytes = static_cast<int>(
        local_events.size() * sizeof(TopologyEventParticipants));
    std::vector<int> byte_counts(amrex::ParallelDescriptor::NProcs());
    MPI_Allgather(&local_bytes, 1, MPI_INT, byte_counts.data(), 1, MPI_INT,
                  amrex::ParallelDescriptor::Communicator());
    std::vector<int> byte_offsets(byte_counts.size(), 0);
    int total_bytes = 0;
    for (std::size_t rank = 0; rank < byte_counts.size(); ++rank) {
      byte_offsets[rank] = total_bytes;
      total_bytes += byte_counts[rank];
    }
    if (total_bytes % static_cast<int>(sizeof(TopologyEventParticipants)) !=
        0) {
      amrex::Abort(topologyReasonCode(
          TopologyReason::simultaneous_topology_conflict));
    }
    all_events.resize(
        total_bytes / static_cast<int>(sizeof(TopologyEventParticipants)));
    MPI_Allgatherv(
        local_events.empty() ? nullptr : local_events.data(),
        local_bytes, MPI_BYTE,
        all_events.empty() ? nullptr : all_events.data(),
        byte_counts.data(), byte_offsets.data(), MPI_BYTE,
        amrex::ParallelDescriptor::Communicator());
#else
    all_events = local_events;
#endif

    int conflict = 0;
    std::unordered_map<std::uint64_t,std::size_t> participant_event;
    for (std::size_t event_index = 0;
         event_index < all_events.size(); ++event_index) {
      const auto& event = all_events[event_index];
      const int ids[2] = {event.first_id, event.second_id};
      const int cpus[2] = {event.first_cpu, event.second_cpu};
      for (int participant = 0; participant < 2; ++participant) {
        if (ids[participant] < 0 && cpus[participant] < 0) continue;
        if (ids[participant] < 0 || cpus[participant] < 0) {
          conflict = 1;
          continue;
        }
        const auto key = particleKey(ids[participant], cpus[participant]);
        const auto inserted = participant_event.emplace(key, event_index);
        if (!inserted.second) conflict = 1;
      }
    }

    // A bond is part of an event's topology footprint when either endpoint
    // participates. If its endpoints belong to two different proposed events,
    // those events share that bond and the complete batch must abort.
    for (int lev = 0; lev <= particles.finestLevel(); ++lev) {
      const auto& level_particles = particles.GetParticles(lev);
      for (const auto& entry : level_particles) {
        const auto& tile = entry.second;
        const int count = tile.numRealParticles();
        const auto& aos = tile.GetArrayOfStructs();
        amrex::Gpu::HostVector<BMXParticleContainer::ParticleType> host(count);
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         aos.begin(), aos.begin() + count, host.begin());
        for (const auto& particle : host) {
          const auto owner = participant_event.find(particleKey(
              particle.idata(intIdx::id), particle.idata(intIdx::cpu)));
          if (owner == participant_event.end()) continue;
          const int bond_count = particle.idata(intIdx::n_bnds);
          if (bond_count < 0 || bond_count > 4) {
            conflict = 1;
            continue;
          }
          for (int bond = 0; bond < bond_count; ++bond) {
            const auto endpoint = participant_event.find(particleKey(
                particle.idata(intIdx::seg1_id1 + bond),
                particle.idata(intIdx::seg1_id2 + bond)));
            if (endpoint != participant_event.end() &&
                endpoint->second != owner->second) {
              conflict = 1;
            }
          }
        }
      }
    }
    amrex::ParallelDescriptor::ReduceIntMax(conflict);
    const auto decision = classifySimultaneousBatch(conflict ? 2 : 1);
    if (decision.disposition == TopologyDisposition::abort_update) {
      amrex::Abort(topologyReasonCode(decision.reason));
    }
  }

  void validateBondTopology (BMXParticleContainer& particles)
  {
    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) return;

    requireRedistributionSafe(particles);

    struct HostParticle
    {
      int id;
      int cpu;
      int bond_count;
      int endpoint_id[4];
      int endpoint_cpu[4];
    };
    std::vector<unsigned long long> local_keys;
    std::vector<HostParticle> local_particles;

    for (int lev = 0; lev <= particles.finestLevel(); ++lev) {
      const auto& level_particles = particles.GetParticles(lev);
      for (const auto& entry : level_particles) {
        const auto& tile = entry.second;
        const int count = tile.numRealParticles();
        const auto& aos = tile.GetArrayOfStructs();
        amrex::Gpu::HostVector<BMXParticleContainer::ParticleType> host(count);
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         aos.begin(), aos.begin() + count, host.begin());
        for (const auto& particle : host) {
          HostParticle record{};
          record.id = particle.idata(intIdx::id);
          record.cpu = particle.idata(intIdx::cpu);
          record.bond_count = particle.idata(intIdx::n_bnds);
          if (record.id < 0 || record.cpu < 0) {
            amrex::Abort(topologyReasonCode(
                TopologyReason::unmapped_particle_deletion));
          }
          for (int bond = 0; bond < 4; ++bond) {
            record.endpoint_id[bond] =
                particle.idata(intIdx::seg1_id1 + bond);
            record.endpoint_cpu[bond] =
                particle.idata(intIdx::seg1_id2 + bond);
          }
          local_keys.push_back(static_cast<unsigned long long>(
              particleKey(record.id, record.cpu)));
          local_particles.push_back(record);
        }
      }
    }

    std::vector<unsigned long long> all_keys;
#ifdef AMREX_USE_MPI
    const int local_count = static_cast<int>(local_keys.size());
    std::vector<int> counts(amrex::ParallelDescriptor::NProcs());
    MPI_Allgather(&local_count, 1, MPI_INT, counts.data(), 1, MPI_INT,
                  amrex::ParallelDescriptor::Communicator());
    std::vector<int> offsets(counts.size(), 0);
    int total_count = 0;
    for (std::size_t rank = 0; rank < counts.size(); ++rank) {
      offsets[rank] = total_count;
      total_count += counts[rank];
    }
    all_keys.resize(total_count);
    MPI_Allgatherv(local_keys.data(), local_count, MPI_UNSIGNED_LONG_LONG,
                   all_keys.data(), counts.data(), offsets.data(),
                   MPI_UNSIGNED_LONG_LONG,
                   amrex::ParallelDescriptor::Communicator());
#else
    all_keys = local_keys;
#endif

    std::unordered_set<std::uint64_t> live_keys;
    for (const auto key : all_keys) {
      if (!live_keys.insert(static_cast<std::uint64_t>(key)).second) {
        amrex::Abort(topologyReasonCode(
            TopologyReason::simultaneous_topology_conflict));
      }
    }

    int invalid_bond_record = 0;
    int orphan_found = 0;
    amrex::Long pruned_relationships = 0;
    for (const auto& particle : local_particles) {
      if (particle.bond_count < 0 || particle.bond_count > 4) {
        invalid_bond_record = 1;
        continue;
      }
      for (int bond = 0; bond < particle.bond_count; ++bond) {
        const auto endpoint = particleKey(
            particle.endpoint_id[bond], particle.endpoint_cpu[bond]);
        if (live_keys.find(endpoint) == live_keys.end()) orphan_found = 1;
        bool redundant =
            particle.endpoint_id[bond] == particle.id &&
            particle.endpoint_cpu[bond] == particle.cpu;
        for (int prior = 0; prior < bond; ++prior) {
          redundant = redundant ||
              (particle.endpoint_id[prior] == particle.endpoint_id[bond] &&
               particle.endpoint_cpu[prior] == particle.endpoint_cpu[bond]);
        }
        if (redundant) ++pruned_relationships;
      }
    }
    amrex::ParallelDescriptor::ReduceIntMax(invalid_bond_record);
    amrex::ParallelDescriptor::ReduceIntMax(orphan_found);
    if (invalid_bond_record || orphan_found) {
      // Current BMX has no bond-owned D/E/F field. A later representation
      // must pass true here if it introduces pending bond material.
      constexpr bool has_pending_material = false;
      const auto decision = classifyOrphanBond(false, has_pending_material);
      amrex::Abort(topologyReasonCode(decision.reason));
    }

    // The complete live-owner/orphan preflight above is intentionally earlier
    // than this mutation. Bonds own no D/E/F in v1, so self-loops and duplicate
    // endpoints are zero-state relationships and may now be pruned canonically.
    for (int lev = 0; lev <= particles.finestLevel(); ++lev) {
      for (BMXParticleContainer::BMXParIter pti(particles, lev);
           pti.isValid(); ++pti) {
        auto& aos = pti.GetArrayOfStructs();
        auto* pstruct = aos().dataPtr();
        const int count = pti.numParticles();
        amrex::ParallelFor(count,
            [=] AMREX_GPU_DEVICE (int index) noexcept
            {
              auto& particle = pstruct[index];
              int* values = &particle.idata(0);
              const int bond_count = values[intIdx::n_bnds];
              int kept = 0;
              for (int bond = 0; bond < bond_count; ++bond) {
                const int endpoint_id = values[intIdx::seg1_id1 + bond];
                const int endpoint_cpu = values[intIdx::seg1_id2 + bond];
                bool redundant =
                    endpoint_id == values[intIdx::id] &&
                    endpoint_cpu == values[intIdx::cpu];
                for (int prior = 0; prior < kept; ++prior) {
                  redundant = redundant ||
                      (values[intIdx::seg1_id1 + prior] == endpoint_id &&
                       values[intIdx::seg1_id2 + prior] == endpoint_cpu);
                }
                if (!redundant) {
                  values[intIdx::seg1_id1 + kept] = endpoint_id;
                  values[intIdx::seg1_id2 + kept] = endpoint_cpu;
                  values[intIdx::site1 + kept] = values[intIdx::site1 + bond];
                  ++kept;
                }
              }
              for (int bond = kept; bond < 4; ++bond) {
                values[intIdx::seg1_id1 + bond] = -1;
                values[intIdx::seg1_id2 + bond] = -1;
                values[intIdx::site1 + bond] = -1;
              }
              values[intIdx::n_bnds] = kept;
            });
      }
    }
    amrex::Gpu::streamSynchronize();
    amrex::ParallelDescriptor::ReduceLongSum(pruned_relationships);
    if (pruned_relationships > 0) {
      amrex::Print() << topologyReasonCode(
          TopologyReason::zero_state_bond_pruned)
                     << " count=" << pruned_relationships << '\n';
    }
  }

  void requireIntegratedConservation (const ParticleTotals& before,
                                      const ParticleTotals& after,
                                      const char* operation)
  {
    const amrex::Real before_values[state_count] =
        {before.d, before.e, before.f};
    const amrex::Real after_values[state_count] =
        {after.d, after.e, after.f};
    const char* const names[state_count] = {"P_D", "P_E", "P_F"};
    for (int state = 0; state < state_count; ++state) {
      const amrex::Real old_amount = before_values[state];
      const amrex::Real new_amount = after_values[state];
      const amrex::Real s_l1 =
          amrex::Math::abs(old_amount) + amrex::Math::abs(new_amount);
      const amrex::Real residual = new_amount - old_amount;
      const amrex::Real tolerance = integratedTolerance(s_l1);
      if (!finite(old_amount) || !finite(new_amount) || !finite(residual) ||
          negativeAboveIntegratedTolerance(old_amount, s_l1) ||
          negativeAboveIntegratedTolerance(new_amount, s_l1) ||
          amrex::Math::abs(residual) > tolerance) {
        std::ostringstream message;
        message.precision(17);
        message << "P10 integrated conservation failure during " << operation
                << " for " << names[state]
                << ": before=" << old_amount
                << " after=" << new_amount
                << " residual=" << residual
                << " tolerance=" << tolerance;
        amrex::Abort(message.str());
      }
    }
  }

  const CumulativeLedger& cumulativeLedger () noexcept
  {
    return ledger_state;
  }

  void resetCumulativeLedger () noexcept
  {
    ledger_state = CumulativeLedger{};
  }

  void creditStructuralP (amrex::Real amount)
  {
    if (!finite(amount) || amount < 0.0) {
      amrex::Abort("P13 structural-P credit must be finite and nonnegative");
    }
    if (amount > 0.0 && !ledger_state.reference_bound) {
      amrex::Abort(
          "P13 structural-P credit requires a bound P10 reference ledger");
    }
    const amrex::Real updated = ledger_state.structural_p + amount;
    if (!finite(updated) || updated < ledger_state.structural_p) {
      amrex::Abort("P13 structural-P cumulative ledger overflow");
    }
    ledger_state.structural_p = updated;
  }

  void creditExportedP (amrex::Real amount)
  {
    if (!finite(amount) || amount < 0.0) {
      amrex::Abort("P14 exported-P credit must be finite and nonnegative");
    }
    if (amount > 0.0 && !ledger_state.reference_bound) {
      amrex::Abort(
          "P14 exported-P credit requires a bound P10 reference ledger");
    }
    const amrex::Real updated = ledger_state.exported_p + amount;
    if (!finite(updated) || updated < ledger_state.exported_p) {
      amrex::Abort("P14 exported-P cumulative ledger overflow");
    }
    ledger_state.exported_p = updated;
  }

  GlobalLedgerSnapshot evaluateGlobalLedger (const ParticleTotals& mesh,
                                             const ParticleTotals& internal,
                                             bool require_bound)
  {
    if (!otherExitLedgerIsZero(ledger_state)) {
      amrex::Abort(
          "P10 v1 prohibits other exits; other_exit_d/e/f/events must remain exactly zero");
    }
    if (!finite(mesh.d) || !finite(mesh.e) || !finite(mesh.f) ||
        !finite(internal.d) || !finite(internal.e) || !finite(internal.f) ||
        !finite(ledger_state.structural_p) ||
        !finite(ledger_state.exported_p) ||
        mesh.e != 0.0) {
      amrex::Abort("P10 global ledger contains nonfinite state or a prohibited mesh P_E amount");
    }
    const amrex::Real inventory_s_l1 =
        amrex::Math::abs(mesh.d) + amrex::Math::abs(mesh.f) +
        amrex::Math::abs(internal.d) + amrex::Math::abs(internal.e) +
        amrex::Math::abs(internal.f) +
        amrex::Math::abs(ledger_state.structural_p) +
        amrex::Math::abs(ledger_state.exported_p);
    if (negativeAboveIntegratedTolerance(mesh.d, inventory_s_l1) ||
        negativeAboveIntegratedTolerance(mesh.f, inventory_s_l1) ||
        negativeAboveIntegratedTolerance(internal.d, inventory_s_l1) ||
        negativeAboveIntegratedTolerance(internal.e, inventory_s_l1) ||
        negativeAboveIntegratedTolerance(internal.f, inventory_s_l1)) {
      amrex::Abort("P10 global ledger contains a negative inventory amount above tolerance");
    }
    GlobalLedgerSnapshot snapshot;
    snapshot.mesh = mesh;
    snapshot.internal = internal;
    snapshot.accounted_total_p = accountedTotal(mesh, internal, ledger_state);
    if (!finite(snapshot.accounted_total_p)) {
      amrex::Abort("P10 global ledger accounted total is nonfinite");
    }
    if (!ledger_state.reference_bound) {
      if (require_bound) {
        amrex::Abort("P10 global ledger reference is unbound at a required audit boundary");
      }
      snapshot.residual = 0.0;
      snapshot.tolerance = integratedTolerance(
          amrex::Math::abs(snapshot.accounted_total_p));
      return snapshot;
    }
    snapshot.residual =
        snapshot.accounted_total_p - ledger_state.reference_total_p;
    const amrex::Real s_l1 =
        amrex::Math::abs(snapshot.accounted_total_p) +
        amrex::Math::abs(ledger_state.reference_total_p);
    snapshot.tolerance = integratedTolerance(s_l1);
    if (!finite(snapshot.residual) ||
        amrex::Math::abs(snapshot.residual) > snapshot.tolerance) {
      std::ostringstream message;
      message.precision(17);
      message << "P10 global ledger residual exceeds tolerance: accounted="
              << snapshot.accounted_total_p
              << " reference=" << ledger_state.reference_total_p
              << " residual=" << snapshot.residual
              << " tolerance=" << snapshot.tolerance;
      amrex::Abort(message.str());
    }
    return snapshot;
  }

  void bindReferenceTotal (const ParticleTotals& mesh,
                           const ParticleTotals& internal)
  {
    const auto snapshot = evaluateGlobalLedger(mesh, internal, false);
    if (snapshot.accounted_total_p < 0.0) {
      amrex::Abort("P10 global ledger cannot bind a negative reference total");
    }
    if (ledger_state.reference_bound) {
      const amrex::Real s_l1 =
          amrex::Math::abs(ledger_state.reference_total_p) +
          amrex::Math::abs(snapshot.accounted_total_p);
      if (amrex::Math::abs(
              ledger_state.reference_total_p - snapshot.accounted_total_p) >
          integratedTolerance(s_l1)) {
        amrex::Abort("P10 global ledger reference cannot be rebound to a different amount");
      }
      return;
    }
    ledger_state.reference_total_p = snapshot.accounted_total_p;
    ledger_state.reference_bound = true;
  }

  void restoreCumulativeLedger (const CumulativeLedger& ledger)
  {
    if (!finite(ledger.reference_total_p) ||
        !finite(ledger.structural_p) || !finite(ledger.exported_p) ||
        !finite(ledger.other_exits.d) || !finite(ledger.other_exits.e) ||
        !finite(ledger.other_exits.f) || ledger.reference_total_p < 0.0 ||
        (!ledger.reference_bound && ledger.reference_total_p != 0.0) ||
        ledger.structural_p < 0.0 ||
        ledger.exported_p < 0.0 || ledger.other_exits.d < 0.0 ||
        ledger.other_exits.e < 0.0 || ledger.other_exits.f < 0.0) {
      amrex::Abort("P10 checkpoint contains a nonfinite or negative cumulative ledger amount");
    }
    if (!otherExitLedgerIsZero(ledger)) {
      amrex::Abort(
          "P10 checkpoint rejected: v1 other_exit_d/e/f/events must be exactly zero");
    }
    ledger_state = ledger;
  }
}
