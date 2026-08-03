//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <bmx.H>
#include <bmx_fluid_parms.H>
#include <bmx_dem_parms.H>
#include <bmx_phosphorus_uptake_K.H>
#include <bmx_phosphorus_export_K.H>
#include <bmx_p15_stage0_K.H>

// This subroutine is the driver for time stepping the whole system
// (fluid + particles )
void
bmx::Evolve (int nstep, Real & dt, Real & prev_dt, Real time, Real stop_time)
{
    BL_PROFILE_REGION_START("bmx::Evolve");

    const bool p15_enabled = BMXP15Stage0::enabled();
    if (p15_enabled && DEM::solve && time == 0.0) {
      // The initial physical network must exist before O01 and before the
      // first O02 terminal-distance construction.  P15 canonicalizes by
      // stable particle key using the inherited endpoint coincidence rule;
      // legacy runs retain their historical initializer below.
      BMXP15Stage0::initializeCanonicalBonds(*pc);
    }

    AuditP10Ledger("O01_PRE_UPDATE_LEDGER", true);

    Real coupling_timing(0.);
    Real drag_timing(0.);

    /****************************************************************************
     *                                                                          *
     * Evolve Fluid and Update Chemistry inside Particles                       *
     *                                                                          *
     ***************************************************************************/
    Real start_fluid = ParallelDescriptor::second();
    BL_PROFILE_VAR("FLUID SOLVE",fluidSolve);
    if (FLUID::solve)
    {
       EvolveFluid(nstep,dt,prev_dt,time,stop_time,drag_timing);
       prev_dt = dt;
    }
    BL_PROFILE_VAR_STOP(fluidSolve);

    Real end_fluid = ParallelDescriptor::second() - start_fluid - drag_timing;
    ParallelDescriptor::ReduceRealMax(end_fluid, ParallelDescriptor::IOProcessorNumber());

#if 0
    const int nchem_species = FLUID::nchem_species;
    for (int lev = 1; lev <= finest_level; lev++)
    {
      auto& ld = *m_leveldata[lev];

#ifdef _OPENMP
#pragma omp parallel if (Gpu::notInLaunchRegion())
#endif
      for (MFIter mfi(*ld.vf_n,TilingIfNotGPU()); mfi.isValid(); ++mfi)
      {
        Box const& bx = mfi.tilebox();

        Array4<Real const> const& vf_n     = ld.vf_n->const_array(mfi);
        Array4<Real const> const& X_k_arr = ld.X_k->const_array(mfi);

        int ix, iy, iz;
        ix = -1;
        iy = -1;
        iz = -1;
        ParallelFor(bx, nchem_species, [&ix,&iy,&iz,vf_n]
            AMREX_GPU_DEVICE (int i, int j, int k, int n) noexcept
            {
              if (vf_n(i,j,k) != 1.0)
              {
                ix = i;
                iy = j;
                iz = k;
              }
            });
        if (ix > -1 && iy > -1 && iz > -1) {
          std::cout << "VF " << vf_n(ix,iy,iz,0) << std::endl;
          std::cout << "XK " << X_k_arr(ix,iy,iz,0) << std::endl;
          std::cout << "XK " << X_k_arr(ix,iy,iz,1) << std::endl;
          std::cout << "XK " << X_k_arr(ix,iy,iz,2) << std::endl;
        }
      } // mfi
    } // lev
#endif


    /****************************************************************************
     *                                                                          *
     * Evolve Particles (Using Particle MD)                                     *
     *                                                                          *
     ***************************************************************************/

    Real start_particles = ParallelDescriptor::second();

    BL_PROFILE_VAR("PARTICLES SOLVE", particlesSolve);

    int nsubsteps;

    if (ParallelDescriptor::IOProcessor()) {
      std::cout<<"Current time in EVOLVE: "<<time<<std::endl;
    }
    if (DEM::solve)
    {
      if (BMXPhosphorusUptake::enabled() && !p15_enabled) {
        // P12 is a hash-bound fixed-network depletion experiment.  Particle
        // mechanics and every topology operator are disabled by contract;
        // O02/O03 uptake and O04 mesh diffusion have already completed in
        // EvolveFluid, so advancing the particles here would change the
        // experiment rather than merely integrate motion.
        nsubsteps = 0;
      } else {
        if (!p15_enabled && time == 0.0) {
          pc->InitBonds(particle_cost, knapsack_weight_type);
        }
//        if (time == 118401.0) pc->PrintConnectivity(particle_cost,knapsack_weight_type);
        pc->EvolveParticles(dt, particle_cost, knapsack_weight_type, nsubsteps);
        pc->split_particles(time);
        // Legacy bonded exchange remains responsible for A/B/C. Enabled P09
        // forces its P_D coefficient to exact zero; C13 then fills O07 with a
        // separate canonical finite-volume D-only graph transaction.
        pc->ParticleExchange(dt, particle_cost, knapsack_weight_type, nsubsteps);
        BMXP15Stage0::applyBondedDTransport(*pc, dt);
        if (pc->EvaluateTipFusion(particle_cost,knapsack_weight_type)) {
          amrex::Print()<<"Completing FUSION step"<<std::endl;
          pc->EvaluateInteriorFusion(particle_cost,knapsack_weight_type);
          pc->CleanupFusion(particle_cost,knapsack_weight_type);
        }
      }
      // P12 deliberately freezes topology and skips mechanics. P14 can still
      // fill O09 on that final topology. Preserve feature-off P12 output by
      // adding the P11 audit in the fixed-network path only when P14 is on.
      if (!BMXPhosphorusUptake::enabled() || p15_enabled ||
          BMXPhosphorusExport::enabled()) {
        pc->AuditP11GeometryEvents(nstep);
        pc->ApplyP14Export(nstep, dt);
      }
        if ((nstep+1)%SPECIES::rg_frequency == 0) {
          RealVect cm;
          pc->CalculateFungalCM(particle_cost, knapsack_weight_type, cm);
          amrex::Print()<<"Fungal Center of Mass: ["<<cm[0]<<","<<cm[1]
            <<","<<cm[2]<<"]"<<std::endl;
          Real rg, masst;
          pc->CalculateFungalRG(particle_cost, knapsack_weight_type, rg, masst);
          amrex::Print()<<"Total Fungal Mass: "<<masst<<std::endl;
          amrex::Print()<<"Fungal Radius of Gyration: "<<rg<<std::endl;
          // --- Bisot-style network observables ---
          // V (total volume) ~ carbon cost; S (total surface area) ~ P uptake
          Real network_V = pc->computeParticleVolume();
          Real network_S = pc->computeParticleArea();
          amrex::Print()<<"Network total volume V (~carbon cost): "<<network_V<<std::endl;
          amrex::Print()<<"Network total surface area S (~P uptake): "<<network_S<<std::endl;
          if (FLUID::nchem_species > P_COMP) {
            Real network_P = pc->computeParticleContent(realIdx::first_data + P_COMP);
            amrex::Print()<<"Network total particle P content: "<<network_P<<std::endl;
          }
          pc->CalculateFungalDensityProfile(particle_cost, knapsack_weight_type,
              SPECIES::dens_prof_bins,SPECIES::dens_prof_max);
        }
    }

    BL_PROFILE_VAR_STOP(particlesSolve);

    Real end_particles = ParallelDescriptor::second() - start_particles;
    ParallelDescriptor::ReduceRealMax(end_particles, ParallelDescriptor::IOProcessorNumber());

    AuditP10Ledger("O10_POST_UPDATE_LEDGER", true);
    ComputeAndPrintSums();

    if (ParallelDescriptor::IOProcessor()) {
      if(FLUID::solve)
        std::cout << "   Time per fluid step      " << end_fluid << std::endl;

      if(DEM::solve)
        std::cout << "   Time per " << nsubsteps
                  << " particle steps " << end_particles << std::endl;

      if((DEM::solve) and FLUID::solve)
        std::cout << "   Coupling time per step   " << coupling_timing << std::endl;
    }

    BL_PROFILE_REGION_STOP("bmx::Evolve");
}
