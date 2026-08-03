//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <AMReX.H>
#include <AMReX_Arena.H>
#include <AMReX_Print.H>

#include <AMReX_ParmParse.H>
#include <AMReX_Utility.H>
#include <AMReX_ParallelDescriptor.H>

#include <bmx_fluid_parms.H>
#include <bmx_chem_species_parms.H>
#include <bmx_chem_layout.H>

namespace FLUID
{
  // Flag to solve fluid equations
  int solve;

  // Flag to solve chem_species fluid equations
  int solve_chem_species(0);

  // Fluid phase chem_species names
  amrex::Vector<std::string> chem_species;

  // ChemSpecies unique identifying code
  std::vector<int> chem_species_id;

  // Total number of fluid chem_species
  int nchem_species(0);

#ifdef NEW_CHEM
  // Initial fluid concentrations of species
  std::vector<amrex::Real> init_conc;

  // Location of top of support layer
  amrex::Real surface_location;
#endif

  // Specified constant gas phase chem_species diffusion coefficients
  std::vector<amrex::Real> D_k0(0);

  // Name to later reference when building inputs for IC/BC regions
  std::string name;


  void Initialize ()
  {
    amrex::ParmParse pp("fluid");

    std::vector<std::string> fluid_name;
    pp.queryarr("solve", fluid_name);

    AMREX_ALWAYS_ASSERT_WITH_MESSAGE(fluid_name.size() == 1,
       "Fluid solver not specified. fluid.solve = ? ");

    // Disable the fluid solver if the fluid is defined as "None"
    if (amrex::toLower(fluid_name[0]).compare("none") == 0 or fluid_name[0] == "0" ) {
      solve = 0;
    } else {
      solve = 1;
      name = fluid_name[0];
    }

    // Location of top of support layer
    pp.get("surface_location",surface_location);

    if (solve)
    {
      amrex::ParmParse ppFluid(name.c_str());

      // Fluid chem_species inputs
      if (ppFluid.contains("chem_species"))
      {
        solve_chem_species = 1;

        ppFluid.getarr("chem_species", chem_species);

        nchem_species = chem_species.size();

        std::string layout_error;
        const auto layout_mode =
            BMXChemLayout::classifyMeshSpecies(chem_species, &layout_error);
        if (layout_mode == BMXChemLayout::MeshMode::invalid) {
          amrex::Abort("P09 fluid schema invalid: " + layout_error);
        }

        amrex::Print() << " " << std::endl;

        amrex::Print() << " Reading in " << chem_species.size() << " chem_species from the inputs file" << std::endl;
        for (int n = 0; n < nchem_species; n++)
           amrex::Print() << "chem_species " << n << " is " << chem_species[n] << std::endl;

        D_k0.resize(nchem_species);

        ppFluid.getarr("chem_species_diff", D_k0);
        if (static_cast<int>(D_k0.size()) != nchem_species) {
          amrex::Abort("fluid.chem_species_diff count must match "
                       "fluid.chem_species count");
        }
        if (layout_mode == BMXChemLayout::MeshMode::enabled &&
            D_k0[6] != 0.0) {
          amrex::Abort("enabled P09 mesh P_F diffusion must be exactly zero");
        }
        for (int n = 0; n < nchem_species; n++)
           amrex::Print() << "diff coeffs for chem_species " << n << " is " << D_k0[n] << std::endl;

        amrex::Print() << " " << std::endl;

#ifdef NEW_CHEM
        ppFluid.getarr("init_conc_species", init_conc);
        if (static_cast<int>(init_conc.size()) != nchem_species) {
          amrex::Abort("fluid.init_conc_species count must match "
                       "fluid.chem_species count");
        }
        for (int n = 0; n < nchem_species; n++)
           amrex::Print() << "Initial concentration for chem_species " << n << " is " << init_conc[n] << std::endl;

        amrex::Print() << " " << std::endl;
#endif

        chem_species_id.resize(nchem_species);
        for (int n = 0; n < nchem_species; ++n) {
          chem_species_id[n] = BMXChemLayout::meshToParticle(n, layout_mode);
        }

        // Preserve the feature-off P07 diagnostic stream byte-for-byte.  The
        // explicit P09 layout declaration is emitted only for the new schema.
        if (layout_mode == BMXChemLayout::MeshMode::enabled) {
          amrex::Print() << "BMX_P09_LAYOUT mode="
                         << BMXChemLayout::modeName(layout_mode)
                         << " mesh_components=" << nchem_species
                         << " particle_components="
                         << BMXChemLayout::particle_components
                         << " layout_id=" << BMXChemLayout::layout_id
                         << std::endl;
        }


      }
    }
  }
}
