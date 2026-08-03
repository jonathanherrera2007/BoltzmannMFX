//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <bmx.H>
#include <bmx_deposition_K.H>
#include <bmx_interp_K.H>
#include <bmx_fluid_parms.H>
#include <AMReX_AmrParticles.H>

#ifdef NEW_CHEM
#include <bmx_chem.H>
#include <bmx_chem_K.H>
#include <bmx_pc_phosphorus.H>
#include <bmx_phosphorus_reactions_K.H>
#include <bmx_phosphorus_uptake_K.H>
#include <bmx_phosphorus_export_K.H>
#include <bmx_p15_stage0_K.H>
#endif

namespace
{
struct P09OneToOneDeposition
{
  int increment_start;

  AMREX_GPU_DEVICE
  void operator() (const BMXParticleContainer::ParticleType& p,
                   amrex::Array4<amrex::Real> const& rho,
                   amrex::GpuArray<amrex::Real,AMREX_SPACEDIM> const& plo,
                   amrex::GpuArray<amrex::Real,AMREX_SPACEDIM> const& dxi)
                   const noexcept
  {
    const int i = static_cast<int>(amrex::Math::floor(
        (p.pos(0) - plo[0]) * dxi[0]));
    const int j = static_cast<int>(amrex::Math::floor(
        (p.pos(1) - plo[1]) * dxi[1]));
    const int k = static_cast<int>(amrex::Math::floor(
        (p.pos(2) - plo[2]) * dxi[2]));

    for (int mesh_comp = 0;
         mesh_comp < BMXChemLayout::enabled_mesh_components; ++mesh_comp) {
      const int particle_comp =
          mesh_comp == 6 ? BMXChemLayout::P_F : mesh_comp;
      rho(i,j,k,mesh_comp) +=
          p.rdata(increment_start + particle_comp);
    }
  }
};

struct P09TrilinearDeposition
{
  int increment_start;

  AMREX_GPU_DEVICE
  void operator() (const BMXParticleContainer::ParticleType& p,
                   amrex::Array4<amrex::Real> const& rho,
                   amrex::GpuArray<amrex::Real,AMREX_SPACEDIM> const& plo,
                   amrex::GpuArray<amrex::Real,AMREX_SPACEDIM> const& dxi)
                   const noexcept
  {
    const amrex::Real lx = (p.pos(0) - plo[0]) * dxi[0] + 0.5;
    const amrex::Real ly = (p.pos(1) - plo[1]) * dxi[1] + 0.5;
    const amrex::Real lz = (p.pos(2) - plo[2]) * dxi[2] + 0.5;

    const int i = static_cast<int>(amrex::Math::floor(lx));
    const int j = static_cast<int>(amrex::Math::floor(ly));
    const int k = static_cast<int>(amrex::Math::floor(lz));

    const amrex::Real wx[2] = {1.0 - (lx-i), lx-i};
    const amrex::Real wy[2] = {1.0 - (ly-j), ly-j};
    const amrex::Real wz[2] = {1.0 - (lz-k), lz-k};
    amrex::GpuArray<amrex::GpuArray<amrex::GpuArray<amrex::Real,2>,2>,2>
        weights;
    amrex::Real total_weight = 0.0;
    for (int ii = 0; ii <= 1; ++ii) {
      for (int jj = 0; jj <= 1; ++jj) {
        for (int kk = 0; kk <= 1; ++kk) {
          weights[ii][jj][kk] = wx[ii]*wy[jj]*wz[kk];
          total_weight += weights[ii][jj][kk];
        }
      }
    }
    for (int ii = 0; ii <= 1; ++ii) {
      for (int jj = 0; jj <= 1; ++jj) {
        for (int kk = 0; kk <= 1; ++kk) {
          weights[ii][jj][kk] /= total_weight;
        }
      }
    }

    for (int kk = 0; kk <= 1; ++kk) {
      for (int jj = 0; jj <= 1; ++jj) {
        for (int ii = 0; ii <= 1; ++ii) {
          for (int mesh_comp = 0;
               mesh_comp < BMXChemLayout::enabled_mesh_components;
               ++mesh_comp) {
            const int particle_comp =
                mesh_comp == 6 ? BMXChemLayout::P_F : mesh_comp;
            amrex::Gpu::Atomic::AddNoRet(
                &rho(i+ii-1, j+jj-1, k+kk-1, mesh_comp),
                weights[ii][jj][kk] *
                    p.rdata(increment_start + particle_comp));
          }
        }
      }
    }
  }
};
}

/**
 * @brief this function transfers data from particles to the continuum chemical
 * species fields defined on the AMR grid
 */
void
bmx::bmx_calc_txfr_fluid (Real /*time*/, Real /*dt*/)
{
  BMXChemistry *bmxchem = BMXChemistry::instance();
  int inc_start = bmxchem->getIntData(intIdx::first_real_inc);
  int start_part_comp = realIdx::first_data + inc_start;
  int start_mesh_comp = 0;
  int        num_comp = FLUID::nchem_species;
  const auto layout_mode =
      BMXChemLayout::classifyMeshSpecies(FLUID::chem_species);
  const bool p09_enabled = layout_mode == BMXChemLayout::MeshMode::enabled;

  // Initialize to zero because the deposition routine will only change values
  // where there are particles (note this is the default)
  bool zero_out_input = true;

  // Here we don't divide the quantity on the mesh after deposition
  // (note the default is true)
  bool vol_weight     = false;

  if (bmx::m_cnc_deposition_scheme == DepositionScheme::one_to_one) {

     if (p09_enabled) {
       ParticleToMesh(*pc,get_X_rhs(),0,finest_level,
                      P09OneToOneDeposition{start_part_comp},
                      zero_out_input, vol_weight);
     } else {
       ParticleToMesh(*pc,get_X_rhs(),0,finest_level,
                      OneToOneDeposition{start_part_comp,start_mesh_comp,num_comp},
                      zero_out_input, vol_weight);
     }

  } else if (bmx::m_cnc_deposition_scheme == DepositionScheme::trilinear) {

     if (p09_enabled) {
       ParticleToMesh(*pc,get_X_rhs(),0,finest_level,
                      P09TrilinearDeposition{start_part_comp},
                      zero_out_input, vol_weight);
     } else {
       ParticleToMesh(*pc,get_X_rhs(),0,finest_level,
                      TrilinearDeposition{start_part_comp,start_mesh_comp,num_comp},
                      zero_out_input, vol_weight);
     }

#if 0
  } else if (bmx::m_cnc_deposition_scheme == DepositionScheme::square_dpvm) {

    ParticleToMesh(*pc,get_X_rhsvf(),0,finest_level,DPVMSquareDeposition());

  } else if (bmx::m_cnc_deposition_scheme == DepositionScheme::true_dpvm) {

    ParticleToMesh(*pc,get_X_rhsvf(),0,finest_level,TrueDPVMDeposition());

  } else if (bmx::m_cnc_deposition_scheme == DepositionScheme::centroid) {

    ParticleToMesh(*pc,get_X_rhsvf(),0,finest_level,CentroidDeposition());
#endif

  } else {
    amrex::Abort("Don't know this deposition_scheme for concentrations!");
  }

#ifdef NEW_CHEM
  // O03 has now committed the extensive P12 mesh debit. The particle
  // increment block is a transient transaction buffer, not an inventory, and
  // must be empty before bonded transport/topology and the O10 audit.
  if (p09_enabled) {
    using BMXParIter = BMXParticleContainer::BMXParIter;
    for (int lev = 0; lev <= finest_level; ++lev) {
      for (BMXParIter pti(*pc, lev); pti.isValid(); ++pti) {
        auto& particles = pti.GetArrayOfStructs();
        auto* pstruct = particles().dataPtr();
        const int np = particles.size();
        amrex::ParallelFor(
            np,
            [pstruct] AMREX_GPU_DEVICE (int pid) noexcept
            {
              auto& particle = pstruct[pid];
              const int base = realIdx::first_data +
                               2 * NUM_PARTICLE_CHEM_COMPONENTS;
              particle.rdata(base + BMXChemLayout::P_D) = 0.0;
              particle.rdata(base + BMXChemLayout::P_E) = 0.0;
              particle.rdata(base + BMXChemLayout::P_F) = 0.0;
            });
      }
    }
    amrex::Gpu::synchronize();
  }
#endif
}

/**
 * @brief this function interpolates fluid chem_species onto particle locations
 */
void
bmx::bmx_calc_txfr_particle (Real time, Real dt)
{
  using BMXParIter = BMXParticleContainer::BMXParIter;

#ifdef NEW_CHEM
  BMXChemistry *bmxchem = BMXChemistry::instance();
  const auto layout_mode =
      BMXChemLayout::classifyMeshSpecies(FLUID::chem_species);
  const bool p09_enabled = layout_mode == BMXChemLayout::MeshMode::enabled;
  const auto p12_config = BMXPhosphorusUptake::config();
  const bool p12_enabled = p12_config.enabled;
  const auto p13_config = BMXPhosphorusReactions::config();
  const bool p13_enabled = p13_config.enabled;
  const auto p15_config = BMXP15Stage0::config();
  const bool p15_enabled = p15_config.enabled;
  if (p13_enabled && !p09_enabled) {
    amrex::Abort("P13 requires the enabled P09 three-state layout");
  }
  if (p12_enabled && p13_enabled && !p15_enabled) {
    amrex::Abort(
        "P12 uptake-only and P13 reaction/growth contracts cannot be enabled in the same run");
  }
  if (p15_enabled &&
      (!p12_enabled || !p13_enabled ||
       !BMXPhosphorusExport::config().enabled)) {
    amrex::Abort(
        "P15 Stage 0 requires P12 uptake, P13 reaction/growth, and P14 export enabled together");
  }
  if (p12_enabled) {
    if (!p09_enabled ||
        m_cnc_deposition_scheme != DepositionScheme::one_to_one) {
      amrex::Abort(
          "P12 shared-donor uptake requires the enabled layout and one_to_one chemistry deposition");
    }
    if (Geom(0).isPeriodic(0) || !Geom(0).isPeriodic(1) ||
        Geom(0).isPeriodic(2)) {
      amrex::Abort(
          "P12 requires x/z nonperiodic no-flux boundaries and periodic y");
    }
    if (finest_level != 0) {
      amrex::Abort(
          "P12 v1 uses one uniform AMR level; grid refinement is run as separate frozen decks");
    }
    if (!p15_enabled) {
      const auto& initial = bmxchem->getParticleInitialConcentrations();
      if (initial.size() != NUM_PARTICLE_CHEM_COMPONENTS ||
          initial[BMXChemLayout::P_D] != 0.0 ||
          initial[BMXChemLayout::P_E] != 0.0 ||
          initial[BMXChemLayout::P_F] != 0.0) {
        amrex::Abort("P12 requires initial internal D/E/F to be exactly zero");
      }
    }
  }
  const BMXP15Stage0::TerminalAreaRecord* p15_terminal_areas = nullptr;
  int p15_terminal_area_count = 0;
  if (p15_enabled) {
    // O02 terminal geometry is constructed exactly once from the immutable
    // current topology, before this routine mutates any amount.
    BMXP15Stage0::prepareTerminalAreas(*pc);
    p15_terminal_areas = BMXP15Stage0::terminalAreaDeviceData();
    p15_terminal_area_count = BMXP15Stage0::terminalAreaRecordCount();
  }
  amrex::Gpu::DeviceVector<Real> chempar_vec;
  bmxchem->getChemParams(chempar_vec);
  Real *chempar = &chempar_vec[0];
#endif
  //
  BL_PROFILE("bmx::bmx_calc_txfr_particle()");

  bmx_set_chem_species_bcs(time, get_X_k(), get_D_k());

  long nparticles = 0;
#ifdef NEW_CHEM
  BMXPhosphorusReactions::StepResult p13_step_total;
  std::uint64_t p13_particles_evaluated = 0;
  std::uint64_t p13_accepted_growth_events = 0;
  std::uint64_t p13_roundoff_clamps = 0;
#endif
  for (int lev = 0; lev <= finest_level; lev++)
  {
    Box domain(geom[lev].Domain());

    bool OnSameGrids = ( (dmap[lev] == (pc->ParticleDistributionMap(lev))) &&
                         (grids[lev].CellEqual(pc->ParticleBoxArray(lev))) );

    nparticles += pc->NumberOfParticlesAtLevel(lev);

    // Pointer to Multifab for interpolation
    MultiFab* interp_ptr;

    // Pointer to Multifab for volume fraction
    MultiFab* interp_vptr;

    // Create Multifab with number of particles in grid cell
    MultiFab temp_npart(grids[lev], dmap[lev], 1, 0);
    temp_npart.setVal(0);
    pc->Increment(temp_npart, lev);
    MultiFab* interp_nptr;

    BL_PROFILE_REGION_START("bmx::bmx_calc_txfr_particle::Gradient");
    BL_PROFILE("bmx::bmx_calc_txfr_particle::Gradient");
    // Follow npart to add gradient data
    MultiFab temp_gx(grids[lev], dmap[lev], FLUID::nchem_species, 1);
    MultiFab temp_gy(grids[lev], dmap[lev], FLUID::nchem_species, 1);
    MultiFab temp_gz(grids[lev], dmap[lev], FLUID::nchem_species, 1);
    compute_grad_X(lev,time,temp_gx,temp_gy,temp_gz);
    // amrex::Print() << "NORM OF GX: " << temp_gx.norm0() << std::endl;
    // amrex::Print() << "NORM OF GY: " << temp_gy.norm0() << std::endl;
    // amrex::Print() << "NORM OF GZ: " << temp_gz.norm0() << std::endl;
    MultiFab* interp_gxptr;
    MultiFab* interp_gyptr;
    MultiFab* interp_gzptr;


#ifdef NEW_CHEM
    const int interp_ng    = 1;    // Only one layer needed for interpolation
    const int interp_ncomp = FLUID::nchem_species;

    if (layout_mode == BMXChemLayout::MeshMode::invalid ||
        m_leveldata[lev]->X_k->nComp() != interp_ncomp ||
        interp_ncomp > NUM_MESH_CHEM_COMPONENTS_MAX) {
      amrex::Abort("P09 calc_txfr_particle requires a validated mesh schema "
                   "with at most seven components");
    }
#endif

    if (OnSameGrids)
    {
      // Store X_k for interpolation
      interp_ptr = new MultiFab(grids[lev], dmap[lev], interp_ncomp, interp_ng, MFInfo());

      // Copy 
      MultiFab::Copy(*interp_ptr,*m_leveldata[lev]->X_k, 0, 0,
                      m_leveldata[lev]->X_k->nComp(), interp_ng);
      interp_ptr->FillBoundary(geom[lev].periodicity());

      // Store vf_n for interpolation
      interp_vptr = new MultiFab(grids[lev], dmap[lev], 1, 1, MFInfo());

      // Copy 
      MultiFab::Copy(*interp_vptr,*m_leveldata[lev]->vf_n, 0, 0,
                      m_leveldata[lev]->vf_n->nComp(), 1);
      interp_vptr->FillBoundary(geom[lev].periodicity());

      // Store n_part for interpolation
      interp_nptr = new MultiFab(grids[lev], dmap[lev], 1, 1, MFInfo());

      // Copy 
      MultiFab::Copy(*interp_nptr,temp_npart, 0, 0, temp_npart.nComp(), 0);
      interp_nptr->FillBoundary(geom[lev].periodicity());

      // Store gx for interpolation
      interp_gxptr = new MultiFab(grids[lev], dmap[lev], interp_ncomp, interp_ng, MFInfo());

      // Copy 
      MultiFab::Copy(*interp_gxptr,temp_gx, 0, 0, temp_gx.nComp(), interp_ng);
      interp_gxptr->FillBoundary(geom[lev].periodicity());

      // Store gy for interpolation
      interp_gyptr = new MultiFab(grids[lev], dmap[lev], interp_ncomp, interp_ng, MFInfo());

      // Copy 
      MultiFab::Copy(*interp_gyptr,temp_gy, 0, 0, temp_gy.nComp(), interp_ng);
      interp_gyptr->FillBoundary(geom[lev].periodicity());

      // Store gz for interpolation
      interp_gzptr = new MultiFab(grids[lev], dmap[lev], interp_ncomp, interp_ng, MFInfo());

      // Copy 
      MultiFab::Copy(*interp_gzptr,temp_gz, 0, 0, temp_gz.nComp(), interp_ng);
      interp_gzptr->FillBoundary(geom[lev].periodicity());

    }
    else
    {
      const BoxArray&            pba = pc->ParticleBoxArray(lev);
      const DistributionMapping& pdm = pc->ParticleDistributionMap(lev);

      // Store X_k for interpolation
      interp_ptr = new MultiFab(pba, pdm, interp_ncomp, interp_ng, MFInfo());

      // Copy 
      interp_ptr->ParallelCopy(*m_leveldata[lev]->X_k, 0, 0,
                                m_leveldata[lev]->X_k->nComp(),
                                interp_ng, interp_ng);

      interp_ptr->FillBoundary(geom[lev].periodicity());

      // Store vf_n for interpolation
      interp_vptr = new MultiFab(pba, pdm, 1, 1, MFInfo());

      // Copy 
      interp_vptr->ParallelCopy(*m_leveldata[lev]->vf_n, 0, 0,
                                m_leveldata[lev]->vf_n->nComp(),
                                1, 1);

      interp_vptr->FillBoundary(geom[lev].periodicity());

      // Store n_part for interpolation
      interp_nptr = new MultiFab(pba, pdm, 1, 1, MFInfo());

      // Copy 
      interp_nptr->ParallelCopy(temp_npart, 0, 0,
                                temp_npart.nComp(),
                                1, 1);

      interp_nptr->FillBoundary(geom[lev].periodicity());

      // Gradient gx,gy,gz for interpolation
      interp_gxptr = new MultiFab(pba, pdm, interp_ncomp, interp_ng, MFInfo());
      interp_gyptr = new MultiFab(pba, pdm, interp_ncomp, interp_ng, MFInfo());
      interp_gzptr = new MultiFab(pba, pdm, interp_ncomp, interp_ng, MFInfo());

      // Copy 
      interp_gxptr->ParallelCopy(temp_gx, 0, 0,
                                temp_gx.nComp(), interp_ng, interp_ng);
      interp_gyptr->ParallelCopy(temp_gy, 0, 0,
                                temp_gy.nComp(), interp_ng, interp_ng);
      interp_gzptr->ParallelCopy(temp_gz, 0, 0,
                                temp_gz.nComp(), interp_ng, interp_ng);

      interp_gxptr->FillBoundary(geom[lev].periodicity());
      interp_gyptr->FillBoundary(geom[lev].periodicity());
      interp_gzptr->FillBoundary(geom[lev].periodicity());
    }
    BL_PROFILE_REGION_STOP("bmx::bmx_calc_txfr_particle::Gradient");

    // P12 uses a two-pass transaction over one immutable mesh pre-state.
    // Pass one sums all requests by donor cell. Pass two below applies the
    // common donor scale, so segment order cannot overdraw a cell.
    MultiFab p12_request_sum(
        interp_ptr->boxArray(), interp_ptr->DistributionMap(), 1, 0);
    p12_request_sum.setVal(0.0);
    if (p12_enabled) {
      const int p12_area_mode = static_cast<int>(p12_config.area_mode);
      const Real p12_area_multiplier = p12_config.area_multiplier;
      const Real p12_j_max = p12_config.j_max;
      const Real p12_k_m = p12_config.k_m;
      for (BMXParIter pti(*pc, lev); pti.isValid(); ++pti) {
        auto& particles = pti.GetArrayOfStructs();
        auto* pstruct = particles().dataPtr();
        const int np = particles.size();
        const auto interp_array = interp_ptr->const_array(pti);
        const auto request_array = p12_request_sum.array(pti);
        const auto dxi_array = geom[lev].InvCellSizeArray();
        const auto plo_array = geom[lev].ProbLoArray();
        amrex::ParallelFor(
            np,
            [pstruct,interp_array,request_array,dxi_array,plo_array,dt,
             p12_area_mode,p12_area_multiplier,p12_j_max,p12_k_m,
             p15_enabled,p15_terminal_areas,p15_terminal_area_count]
            AMREX_GPU_DEVICE (int pid) noexcept
            {
              auto& particle = pstruct[pid];
              const int i = static_cast<int>(amrex::Math::floor(
                  (particle.pos(0) - plo_array[0]) * dxi_array[0]));
              const int j = static_cast<int>(amrex::Math::floor(
                  (particle.pos(1) - plo_array[1]) * dxi_array[1]));
              const int k = static_cast<int>(amrex::Math::floor(
                  (particle.pos(2) - plo_array[2]) * dxi_array[2]));
              const Real area = p15_enabled
                  ? BMXP15Stage0::terminalEligibleArea(
                        p15_terminal_areas, p15_terminal_area_count,
                        particle.idata(intIdx::id),
                        particle.idata(intIdx::cpu),
                        particle.idata(intIdx::cell_type) == cellType::FUNGI,
                        p12_area_mode, p12_area_multiplier)
                  : BMXPhosphorusUptake::eligibleArea(
                        particle.rdata(realIdx::area),
                        particle.rdata(realIdx::c_length),
                        particle.idata(intIdx::position) == siteLocation::TIP,
                        static_cast<BMXPhosphorusUptake::AreaMode>(p12_area_mode),
                        p12_area_multiplier);
              const Real request = BMXPhosphorusUptake::requestedAmount(
                  interp_array(i,j,k,BMXChemLayout::P_D), area, dt,
                  p12_j_max, p12_k_m);
              amrex::Gpu::Atomic::AddNoRet(
                  &request_array(i,j,k), request);
            });
      }
      amrex::Gpu::synchronize();
    }

    Gpu::DeviceScalar<Real> p12_requested_gpu(0.0);
    Gpu::DeviceScalar<Real> p12_accepted_gpu(0.0);
    Gpu::DeviceScalar<Real> p12_area_gpu(0.0);
    Gpu::DeviceScalar<Real> p12_min_scale_gpu(1.0);
    Gpu::DeviceScalar<Real> p12_max_eta_gpu(0.0);
    Gpu::DeviceScalar<int> p12_zero_inventory_request_gpu(0);
    Real* p12_requested = p12_requested_gpu.dataPtr();
    Real* p12_accepted = p12_accepted_gpu.dataPtr();
    Real* p12_area = p12_area_gpu.dataPtr();
    Real* p12_min_scale = p12_min_scale_gpu.dataPtr();
    Real* p12_max_eta = p12_max_eta_gpu.dataPtr();
    int* p12_zero_inventory_request =
        p12_zero_inventory_request_gpu.dataPtr();
    Gpu::DeviceScalar<BMXPhosphorusReactions::DeviceAccumulator>
        p13_accumulator_gpu(BMXPhosphorusReactions::DeviceAccumulator{});
    auto* p13_accumulator = p13_accumulator_gpu.dataPtr();

    BL_PROFILE_REGION_START("bmx::bmx_calc_txfr_particle::Particles");
    BL_PROFILE("bmx::bmx_calc_txfr_particle::Particles");
#ifdef _OPENMP
#pragma omp parallel if (Gpu::notInLaunchRegion())
#endif
    {
      const auto dx_array  = geom[lev].CellSizeArray();
      const auto dxi_array = geom[lev].InvCellSizeArray();
      const auto plo_array = geom[lev].ProbLoArray();

      const amrex::RealVect  dx( dx_array[0],  dx_array[1],  dx_array[2]);
      const amrex::RealVect dxi(dxi_array[0], dxi_array[1], dxi_array[2]);
      const amrex::RealVect plo(plo_array[0], plo_array[1], plo_array[2]);

      Real grid_vol = dx[0]*dx[1]*dx[2];

      if (m_verbose != 0) {
        for (BMXParIter pti(*pc, lev); pti.isValid(); ++pti)
        {
          auto& particles = pti.GetArrayOfStructs();
          BMXParticleContainer::ParticleType* pstruct = particles().dataPtr();

          const int np = particles.size();

          for (int pid=0; pid<np; pid++) {
              // Local array storing interpolated values

              BMXParticleContainer::ParticleType& p = pstruct[pid];
              Real *cell_par = &p.rdata(0);
              Real *p_vals = &p.rdata(realIdx::first_data);
              bmxchem->printCellConcentrations((int)p.id(), p_vals, cell_par);
          }
        }
      }

      for (BMXParIter pti(*pc, lev); pti.isValid(); ++pti)
      {
        auto& particles = pti.GetArrayOfStructs();
        BMXParticleContainer::ParticleType* pstruct = particles().dataPtr();

        const int np = particles.size();

        const auto& interp_array = interp_ptr->array(pti);

        const auto& interp_varray = interp_vptr->array(pti);

        const auto& interp_narray = interp_nptr->array(pti);

        const auto& interp_gxarray = interp_gxptr->array(pti);
        const auto& interp_gyarray = interp_gyptr->array(pti);
        const auto& interp_gzarray = interp_gzptr->array(pti);
        const auto& p12_request_array = p12_request_sum.const_array(pti);
        
        /* Add interp_garray for gradients */

        int l_cnc_deposition_scheme;
        if (bmx::m_cnc_deposition_scheme == DepositionScheme::one_to_one) 
             l_cnc_deposition_scheme = 0;
        else if (bmx::m_cnc_deposition_scheme == DepositionScheme::trilinear) 
             l_cnc_deposition_scheme = 1;
        else 
           amrex::Abort("Dont know this deposition scheme in calc_txfr_particle");

        int l_vf_deposition_scheme;
        if (bmx::m_vf_deposition_scheme == DepositionScheme::one_to_one) 
             l_vf_deposition_scheme = 0;
        else if (bmx::m_vf_deposition_scheme == DepositionScheme::trilinear) 
             l_vf_deposition_scheme = 1;
        else 
           amrex::Abort("Dont know this deposition scheme in calc_txfr_particle");

        int nloop = m_nloop;
        amrex::ParallelFor(np,
            [pstruct,interp_array,interp_varray,interp_narray,plo,dxi,grid_vol,dt,
             nloop,chempar,l_cnc_deposition_scheme,l_vf_deposition_scheme,interp_gxarray,
               interp_ncomp,p09_enabled,p12_enabled,p13_enabled,p15_enabled,
               p15_terminal_areas,p15_terminal_area_count,
              p12_request_array,
              p12_requested,p12_accepted,p12_area,p12_min_scale,p12_max_eta,
              p12_zero_inventory_request,
              p13_accumulator,
             p12_area_mode=static_cast<int>(p12_config.area_mode),
             p12_area_multiplier=p12_config.area_multiplier,
             p12_j_max=p12_config.j_max,p12_k_m=p12_config.k_m,
             p13_reactions_enabled=p13_config.reactions_enabled,
             p13_growth_enabled=p13_config.growth_enabled,
             p13_k_de=p13_config.k_de,p13_k_ed=p13_config.k_ed,
             p13_q_p=p13_config.q_p,
             p13_k_gp_over_k_gb=p13_config.k_gp_over_k_gb,
            interp_gyarray,interp_gzarray]
            AMREX_GPU_DEVICE (int pid) noexcept
              {
#if 0
              std::printf("chempar[0]: %f\n",chempar[0]);
              std::printf("chempar[1]: %f\n",chempar[1]);
              std::printf("chempar[2]: %f\n",chempar[2]);
              std::printf("chempar[3]: %f\n",chempar[3]);
              std::printf("chempar[4]: %f\n",chempar[4]);
              std::printf("chempar[5]: %f\n",chempar[5]);
              std::printf("chempar[6]: %f\n",chempar[6]);
              std::printf("chempar[7]: %f\n",chempar[7]);
              std::printf("chempar[8]: %f\n",chempar[8]);
              std::printf("chempar[9]: %f\n",chempar[9]);
              std::printf("chempar[10]: %f\n",chempar[10]);
              std::printf("chempar[11]: %f\n",chempar[11]);
              std::printf("chempar[12]: %f\n",chempar[12]);
              std::printf("chempar[13]: %f\n",chempar[13]);
              std::printf("chempar[14]: %f\n",chempar[14]);
              std::printf("chempar[15]: %f\n",chempar[15]);
              std::printf("chempar[16]: %f\n",chempar[16]);
              std::printf("chempar[17]: %f\n",chempar[17]);
              std::printf("chempar[18]: %f\n",chempar[18]);
              std::printf("chempar[19]: %f\n",chempar[19]);
              std::printf("chempar[20]: %f\n",chempar[20]);
#endif
              // Local array storing interpolated values
              GpuArray<Real, NUM_MESH_CHEM_COMPONENTS_MAX> interp_mesh_loc{};
              GpuArray<Real, NUM_PARTICLE_CHEM_COMPONENTS> interp_loc{};

              // Array storing volume fraction
              GpuArray<Real, 1> interp_vloc;

              // Array storing number of particles
              GpuArray<Real, 1> interp_nloc;

              // Arrays storing chemical gradient
              GpuArray<Real, 1> interp_gxloc;
              GpuArray<Real, 1> interp_gyloc;
              GpuArray<Real, 1> interp_gzloc;

              BMXParticleContainer::ParticleType& p = pstruct[pid];

              if (l_cnc_deposition_scheme == 0)
              {
                  one_to_one_interp(p.pos(), &interp_mesh_loc[0],
                                    interp_array, plo, dxi, interp_ncomp);
              }
              else if (l_cnc_deposition_scheme == 1)
              {
                  trilinear_interp(p.pos(), &interp_mesh_loc[0],
                                   interp_array, plo, dxi, interp_ncomp);
              }
              for (int mesh_comp = 0; mesh_comp < interp_ncomp; ++mesh_comp) {
                const int particle_comp =
                    (p09_enabled && mesh_comp == 6)
                        ? BMXChemLayout::P_F : mesh_comp;
                interp_loc[particle_comp] = interp_mesh_loc[mesh_comp];
              }
              if (l_vf_deposition_scheme == 0)
              {
                  one_to_one_interp(p.pos(), &interp_vloc[0],
                                    interp_varray, plo, dxi, 1);
              }
              else if (l_vf_deposition_scheme == 1)
              {
                  trilinear_interp(p.pos(), &interp_vloc[0],
                                   interp_varray, plo, dxi, 1);
              }
              one_to_one_interp(p.pos(), &interp_nloc[0],
                  interp_narray, plo, dxi, 1);
              one_to_one_interp(p.pos(), &interp_gxloc[0],
                  interp_gxarray, plo, dxi, 1);
              one_to_one_interp(p.pos(), &interp_gyloc[0],
                  interp_gyarray, plo, dxi, 1);
              one_to_one_interp(p.pos(), &interp_gzloc[0],
                  interp_gzarray, plo, dxi, 1);

#ifndef AMREX_USE_GPU
              //std::cout<<"Number of particles in grid cell: "<<interp_nloc[0]<<std::endl;
#endif
#ifdef NEW_CHEM
              Real *cell_par = &p.rdata(0);

              // Store chemical gradient data here. It will be used in particle
              // splitting routine
              cell_par[realIdx::gx] = interp_gxloc[0];
              cell_par[realIdx::gy] = interp_gyloc[0];
              cell_par[realIdx::gz] = interp_gzloc[0];

              Real *p_vals = &p.rdata(realIdx::first_data);
              int *cell_ipar = &p.idata(0);
              if (interp_nloc[0] == 0.0) amrex::Abort("Number of particles is Zero!");
              BMXPhosphorus::ParticleAmounts phosphorus_before;
              if (p09_enabled &&
                  BMXPhosphorus::captureParticleAmounts(
                      cell_par, phosphorus_before) !=
                      BMXPhosphorus::AmountStatus::ok) {
                amrex::Abort(
                    "P10 pure-volume update encountered invalid D/E/F amount state");
              }
#if 0
              printf("   fluid volume fraction    : %16.8e\n",interp_vloc[0]);
              printf("   grid cell volume         : %16.8e\n",grid_vol);
              printf("   number of particles/cell : %16.8f\n",interp_nloc[0]);
              printf("   fluid volume per particle: %16.8e\n",grid_vol*interp_vloc[0]/interp_nloc[0]);
              printf("   time increment           : %16.8e\n",dt);
#endif
              GpuArray<Real, 25> p13_kernel_parameters{};
              Real* kernel_parameters = chempar;
              if (p13_enabled &&
                  cell_ipar[intIdx::cell_type] == cellType::FUNGI) {
                for (int parameter = 0; parameter < 25; ++parameter) {
                  p13_kernel_parameters[parameter] = chempar[parameter];
                }
                // P13 owns fungal growth in O02. The frozen kernel still
                // executes all earlier legacy transfer/reaction work, but its
                // B-only growth and inert-P limiter are disabled for this
                // feature-on transaction.
                p13_kernel_parameters[14] = 0.0;
                p13_kernel_parameters[15] = 0.0;
                p13_kernel_parameters[23] = 0.0;
                p13_kernel_parameters[24] = 0.0;
                kernel_parameters = &p13_kernel_parameters[0];
              }
              xferMeshToParticleAndUpdateChem(
                  grid_vol*interp_vloc[0], interp_nloc[0], cell_par,
                  &interp_loc[0], p_vals, dt, nloop, kernel_parameters,
                  cell_ipar);
              if (p09_enabled) {
                amrex::Real* owners[1] = {cell_par};
                if (BMXPhosphorus::writePartition(
                        phosphorus_before, owners, 1) !=
                    BMXPhosphorus::AmountStatus::ok) {
                  amrex::Abort(
                    "P10 pure-volume update failed to restore D/E/F amounts");
                }
              }
              if (p12_enabled) {
                const int i = static_cast<int>(amrex::Math::floor(
                    (p.pos(0) - plo[0]) * dxi[0]));
                const int j = static_cast<int>(amrex::Math::floor(
                    (p.pos(1) - plo[1]) * dxi[1]));
                const int k = static_cast<int>(amrex::Math::floor(
                    (p.pos(2) - plo[2]) * dxi[2]));
                const Real area = p15_enabled
                    ? BMXP15Stage0::terminalEligibleArea(
                          p15_terminal_areas, p15_terminal_area_count,
                          cell_ipar[intIdx::id], cell_ipar[intIdx::cpu],
                          cell_ipar[intIdx::cell_type] == cellType::FUNGI,
                          p12_area_mode, p12_area_multiplier)
                    : BMXPhosphorusUptake::eligibleArea(
                          cell_par[realIdx::area],
                          cell_par[realIdx::c_length],
                          cell_ipar[intIdx::position] == siteLocation::TIP,
                          static_cast<BMXPhosphorusUptake::AreaMode>(p12_area_mode),
                          p12_area_multiplier);
                const Real request = BMXPhosphorusUptake::requestedAmount(
                    interp_array(i,j,k,BMXChemLayout::P_D), area, dt,
                    p12_j_max, p12_k_m);
                const Real request_sum = p12_request_array(i,j,k);
                const Real donor =
                    interp_array(i,j,k,BMXChemLayout::P_D) > 0.0
                        ? interp_array(i,j,k,BMXChemLayout::P_D) : 0.0;
                const Real fluid_fraction = interp_varray(i,j,k) > 0.0
                                                ? interp_varray(i,j,k) : 0.0;
                const Real available = donor * fluid_fraction * grid_vol;
                const Real scale = BMXPhosphorusUptake::donorScale(
                    available, request_sum);
                const Real eta = BMXPhosphorusUptake::donorDemandRatio(
                    available, request_sum);
                const Real accepted = request * scale;
                if (!BMXPhosphorusUptake::finite(request) ||
                    !BMXPhosphorusUptake::finite(request_sum) ||
                    !BMXPhosphorusUptake::finite(available) ||
                    !BMXPhosphorusUptake::finite(eta) ||
                    !BMXPhosphorusUptake::finite(accepted) ||
                    request_sum < 0.0 || available < 0.0 || eta < 0.0 ||
                    area < 0.0 || accepted < 0.0 || accepted > request ||
                    !(cell_par[realIdx::vol] > 0.0)) {
                  amrex::Abort("P12 uptake transaction produced invalid state");
                }
                p_vals[BMXChemLayout::P_D] +=
                    accepted / cell_par[realIdx::vol];
                p_vals[2 * NUM_PARTICLE_CHEM_COMPONENTS +
                       BMXChemLayout::P_D] = -accepted;
                amrex::Gpu::Atomic::AddNoRet(p12_requested, request);
                amrex::Gpu::Atomic::AddNoRet(p12_accepted, accepted);
                amrex::Gpu::Atomic::AddNoRet(p12_area, area);
                if (request > 0.0) {
                  amrex::Gpu::Atomic::Min(p12_min_scale, scale);
                  if (available > 0.0) {
                    amrex::Gpu::Atomic::Max(p12_max_eta, eta);
                  } else {
                    amrex::Gpu::Atomic::Max(p12_zero_inventory_request, 1);
                  }
                }
              }
              if (p13_enabled) {
                const auto step = BMXPhosphorusReactions::apply(
                    cell_par, cell_ipar, dt, p13_reactions_enabled,
                    p13_growth_enabled, p13_k_de, p13_k_ed, p13_q_p,
                    p13_k_gp_over_k_gb, chempar[14], chempar[15],
                    chempar[19], chempar[20]);
                BMXPhosphorusReactions::accumulate(step, p13_accumulator);
              }
#endif
            });
      } // pti
    } // omp region
    BL_PROFILE_REGION_STOP("bmx::bmx_calc_txfr_particle::Particles");

    if (p12_enabled) {
      amrex::Gpu::synchronize();
      BMXPhosphorusUptake::recordAcceptedStep(
          p12_requested_gpu.dataValue(), p12_accepted_gpu.dataValue(),
          p12_area_gpu.dataValue(), dt, p12_min_scale_gpu.dataValue(),
          p12_max_eta_gpu.dataValue(),
          p12_zero_inventory_request_gpu.dataValue());
    }
    if (p13_enabled) {
      amrex::Gpu::synchronize();
      const auto accumulator = p13_accumulator_gpu.dataValue();
      int maximum_status = accumulator.maximum_status;
      amrex::ParallelDescriptor::ReduceIntMax(maximum_status);
      if (maximum_status != static_cast<int>(
              BMXPhosphorusReactions::StepStatus::ok)) {
        amrex::Abort("P13 transaction failed with status " +
                     std::to_string(maximum_status));
      }
      p13_step_total.reaction_forward += accumulator.reaction_forward;
      p13_step_total.reaction_reverse += accumulator.reaction_reverse;
      p13_step_total.carbon_supported_growth +=
          accumulator.carbon_supported_growth;
      p13_step_total.phosphorus_supported_growth +=
          accumulator.phosphorus_supported_growth;
      p13_step_total.requested_growth += accumulator.requested_growth;
      p13_step_total.accepted_growth += accumulator.accepted_growth;
      p13_step_total.rejected_growth += accumulator.rejected_growth;
      p13_step_total.b_debit += accumulator.b_debit;
      p13_step_total.e_debit += accumulator.e_debit;
      p13_step_total.structuralized_p += accumulator.structuralized_p;
      p13_particles_evaluated += static_cast<std::uint64_t>(
          accumulator.particles_evaluated);
      p13_accepted_growth_events += static_cast<std::uint64_t>(
          accumulator.accepted_growth_events);
      p13_roundoff_clamps += static_cast<std::uint64_t>(
          accumulator.roundoff_clamps);
    }

    delete interp_ptr;
    delete interp_vptr;
    delete interp_nptr;
    delete interp_gxptr;
    delete interp_gyptr;
    delete interp_gzptr;

  } // lev
  if (p13_enabled) {
    BMXPhosphorusReactions::recordStep(
        p13_step_total, p13_particles_evaluated,
        p13_accepted_growth_events, p13_roundoff_clamps);
  }
  amrex::Print() << "TOTAL PARTICLES "<<nparticles<<std::endl;
}
