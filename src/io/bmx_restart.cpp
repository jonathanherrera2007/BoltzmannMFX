//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <AMReX_MultiFab.H>
#include <AMReX_PlotFileUtil.H>
#include <AMReX_VisMF.H>    // amrex::VisMF::Write(MultiFab)
#include <AMReX_VectorIO.H> // amrex::[read,write]IntData(array_of_ints)
#include <AMReX_AmrCore.H>
#include <AMReX_buildInfo.H>
#include <AMReX_Geometry.H>

#include <bmx.H>
#include "bmx_checkpoint_schema.H"
#include <bmx_fluid_parms.H>
#include <bmx_dem_parms.H>
#include <bmx_pc_phosphorus.H>
#include <bmx_phosphorus_geometry_K.H>

#include <cmath>

namespace
{
    const std::string level_prefix {"Level_"};
}

void
bmx::Restart (std::string& restart_file, int *nstep, Real *dt, Real *time)
{
    p10_restart_metadata_expected = true;
    if (ooo_debug) amrex::Print() << "Restart" << std::endl;
    BL_PROFILE("bmx::Restart()");

    amrex::Print() << "  Restarting from checkpoint " << restart_file << std::endl;

    Real prob_lo[BL_SPACEDIM];
    Real prob_hi[BL_SPACEDIM];


    /***************************************************************************
     * Load header: set up problem domain (including BoxArray)                 *
     *              load particle data                                         *
     *              allocate bmx memory (bmx::AllocateArrays)                *
     ***************************************************************************/

    {
      std::string File(restart_file + "/Header");

      VisMF::IO_Buffer io_buffer(VisMF::GetIOBufferSize());

      Vector<char> fileCharPtr;
      ParallelDescriptor::ReadAndBcastFile(File, fileCharPtr);
      std::string fileCharPtrString(fileCharPtr.dataPtr());
      std::istringstream is(fileCharPtrString, std::istringstream::in);

      std::string line;

      auto reject_header = [](const std::string& reason)
      {
        amrex::Abort(
            "P09 checkpoint rejected before particle deserialization: " +
            reason);
      };

      auto read_scalar_line = [&is, &reject_header](auto& value,
                                                    const char* field)
      {
        std::string scalar_line;
        if (!std::getline(is, scalar_line)) {
          reject_header(std::string("missing ") + field);
        }
        std::istringstream values(scalar_line);
        std::string extra;
        if (!(values >> value) || (values >> extra)) {
          reject_header(std::string("malformed ") + field);
        }
      };

      auto read_geometry_line = [&is, &reject_header](Real* values,
                                                      const char* field)
      {
        std::string geometry_line;
        if (!std::getline(is, geometry_line)) {
          reject_header(std::string("missing ") + field);
        }
        std::istringstream coordinates(geometry_line);
        for (int direction = 0; direction < BL_SPACEDIM; ++direction) {
          if (!(coordinates >> values[direction]) ||
              !std::isfinite(values[direction])) {
            reject_header(std::string("malformed ") + field);
          }
        }
        std::string extra;
        if (coordinates >> extra) {
          reject_header(std::string("extra coordinates in ") + field);
        }
      };

      std::getline(is, line);
      BMXCheckpointSchema::validateVersionLine(line);
      const auto checkpoint_mode =
          BMXChemLayout::classifyMeshSpecies(FLUID::chem_species);
      const auto checkpoint_geometry =
          BMXCheckpointSchema::readValidateAndRestoreMetadata(
              is, checkpoint_mode, FLUID::chem_species, Geom(0));

      int nlevs = 0;
      read_scalar_line(nlevs, "level count");
      if (nlevs <= 0 || nlevs > maxLevel()+1) {
        reject_header("invalid level count");
      }

      // Time stepping controls
      read_scalar_line(*nstep, "step number");
      read_scalar_line(*dt, "time-step size");
      read_scalar_line(*time, "simulation time");
      const bool valid_initial_dt = (*nstep == 0 && *dt == -1.0);
      if (*nstep < 0 || !std::isfinite(*dt) ||
          (!valid_initial_dt && *dt <= 0.0) ||
          !std::isfinite(*time) || *time < 0.0) {
        reject_header("invalid time-stepping controls");
      }

      read_geometry_line(prob_lo, "prob_lo");
      read_geometry_line(prob_hi, "prob_hi");
      BMXCheckpointSchema::validateGeometryLines(
          checkpoint_geometry, prob_lo, prob_hi);
      for (int direction = 0; direction < BL_SPACEDIM; ++direction) {
        if (prob_hi[direction] <= prob_lo[direction]) {
          reject_header("prob_hi must be greater than prob_lo");
        }
      }

        Vector<BoxArray> checkpoint_box_arrays(nlevs);
        for (int lev = 0; lev < nlevs; ++lev) {

            RealBox rb(prob_lo,prob_hi);
            Geom(lev).ProbDomain(rb);
            Geom(lev).ResetDefaultProbDomain(rb);

            BMXPhosphorusGeometry::loadAndValidate(
                Geom(lev), FLUID::chem_species);

            checkpoint_box_arrays[lev].readFrom(is);
            if (!is.good()) reject_header("malformed BoxArray");
            GotoNextLine(is);

            if (FLUID::solve) AllocateArrays(lev);
        }

        // Only deserialize particles after the complete BMX header has passed
        // schema, scalar, geometry, and BoxArray validation.
        if (DEM::solve) {
          // Pinned AMReX's non-virtual Restart implementation redistributes
          // internally before returning. Scan its native checkpoint payload
          // first so invalid identities or unresolved nonperiodic positions
          // cannot be compacted before the C08 guard observes them.
          BMXPhosphorus::requireCheckpointParticlesSafe(
              *pc, restart_file, "particles");
          pc->Restart(restart_file, "particles");
          amrex::Print() << "  Finished reading particle data" << std::endl;
        }
    }

    amrex::Print() << "  Finished reading header" << std::endl;

    /***************************************************************************
     * Load fluid data                                                         *
     ***************************************************************************/
    if (FLUID::solve)
    {
       // Load the field data
       for (int lev = 0, nlevs=finestLevel()+1; lev < nlevs; ++lev)
       {
           // Read scalar variables
           ResetIOChkData();

           if (advect_fluid_chem_species)
           {
              for (int i = 0; i < chkChemSpeciesVars.size(); i++ )
              {
                 amrex::Print() << "  Loading " << chkChemSpeciesVarsName[i] << " at level " << lev << std::endl;
                 (chkChemSpeciesVars[i][lev])->setVal(0.);
    
                 MultiFab mf;
                 VisMF::Read(mf,
                         amrex::MultiFabFileFullPrefix(lev,
                                                   restart_file, level_prefix,
                                                   chkChemSpeciesVarsName[i]),
                                                   nullptr,
                                                   ParallelDescriptor::IOProcessorNumber());

                 // Copy from the mf we used to read in to the mf we will use going forward
                 (*(chkChemSpeciesVars[i][lev])).ParallelCopy(mf, 0, 0, FLUID::nchem_species,0,0);
              }
              {
                 amrex::Print() << "  Loading volume fraction " << " at level " << lev << std::endl;
    
                 MultiFab mf;
                 VisMF::Read(mf,
                         amrex::MultiFabFileFullPrefix(lev,
                                                   restart_file, level_prefix, "volfrac"),
                                                   nullptr,
                                                   ParallelDescriptor::IOProcessorNumber());

                 // Copy from the mf we used to read in to the mf we will use going forward
                 MultiFab* vf_n = m_leveldata[lev]->vf_n;
                 vf_n->setVal(0.);
                 vf_n->ParallelCopy(mf, 0, 0, 1, 0, 0);
              }
          }
       }

       amrex::Print() << "  Finished reading fluid data" << std::endl;
    }

    // Make sure that the particle BoxArray is the same as the mesh data -- we can
    //      create a dual grid decomposition in the regrid operation
    if (DEM::solve)
    {
        for (int lev = 0; lev <= finestLevel(); lev++)
        {
          pc->SetParticleBoxArray       (lev, grids[lev]);
          pc->SetParticleDistributionMap(lev,  dmap[lev]);
        }
        BMXPhosphorus::requireRedistributionSafe(*pc);
        pc->Redistribute();

       // We need to do this on restart regardless of whether we replicate
       BMXPhosphorus::requireRedistributionSafe(*pc);
       pc->Redistribute();
    }

    if (FLUID::solve)
    {
        for (int lev = 0; lev <= finestLevel(); lev++)
        {
          // Fill the bc's just in case
          m_leveldata[lev]->X_k->FillBoundary(geom[lev].periodicity());
          m_leveldata[lev]->D_k->FillBoundary(geom[lev].periodicity());
        }
    }

    if (load_balance_type == "KnapSack" or load_balance_type == "SFC")
    {
      if (DEM::solve) {
        for (int lev(0); lev < particle_cost.size(); ++lev)
          if (particle_cost[lev] != nullptr)
            delete particle_cost[lev];

        particle_cost.clear();
        particle_cost.resize(finestLevel()+1, nullptr);

        for (int lev = 0; lev <= finestLevel(); lev++)
        {
          particle_cost[lev] = new MultiFab(pc->ParticleBoxArray(lev),
                                                         pc->ParticleDistributionMap(lev), 1, 0);
          particle_cost[lev]->setVal(0.0);
        }
      }
      if (FLUID::solve) {
        for (int lev(0); lev < fluid_cost.size(); ++lev)
          if (fluid_cost[lev] != nullptr)
            delete fluid_cost[lev];

        fluid_cost.clear();
        fluid_cost.resize(finestLevel()+1, nullptr);

        for (int lev = 0; lev <= finestLevel(); lev++)
        {
          fluid_cost[lev] = new MultiFab(grids[lev], dmap[lev], 1, 0);
          fluid_cost[lev]->setVal(0.0);
        }
      }
    }
    amrex::Print() << "  Done with bmx::Restart " << std::endl;
}
