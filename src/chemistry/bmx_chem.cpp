//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <stdio.h>
#include <bmx.H>
#include <bmx_fluid_parms.H>
#include <bmx_chem.H>

amrex::Real BMXChemistry::k1 = 0.0;
amrex::Real BMXChemistry::k2 = 0.0;
amrex::Real BMXChemistry::k3 = 0.0;
amrex::Real BMXChemistry::k4 = 0.0;
amrex::Real BMXChemistry::k5 = 0.0;
amrex::Real BMXChemistry::k6 = 0.0;
amrex::Real BMXChemistry::k7 = 0.0;
amrex::Real BMXChemistry::kP = 0.0;
amrex::Real BMXChemistry::kr1 = 0.0;
amrex::Real BMXChemistry::kr2 = 0.0;
amrex::Real BMXChemistry::kr3 = 0.0;
amrex::Real BMXChemistry::kr4 = 0.0;
amrex::Real BMXChemistry::kr5 = 0.0;
amrex::Real BMXChemistry::kr6 = 0.0;
amrex::Real BMXChemistry::kr7 = 0.0;
amrex::Real BMXChemistry::krP = 0.0;
amrex::Real BMXChemistry::kg = 0.0;
amrex::Real BMXChemistry::kv = 0.0;
amrex::Real BMXChemistry::kb = 0.0;
amrex::Real BMXChemistry::kbv = 0.0;
amrex::Real BMXChemistry::p_growth_limit = 0.0;
amrex::Real BMXChemistry::qP = 0.0;
amrex::Real BMXChemistry::mtA = 0.0;
amrex::Real BMXChemistry::mtB = 0.0;
amrex::Real BMXChemistry::mtC = 0.0;
amrex::Real BMXChemistry::mtP = 0.0;
amrex::Real BMXChemistry::bacteria_radius_max = 0.0;
amrex::Real BMXChemistry::radius_max = 0.0;
amrex::Real BMXChemistry::length_max = 0.0;
amrex::Real BMXChemistry::p_overlap = 0.0;
amrex::Real BMXChemistry::fusion_prob= 0.0;
amrex::Real BMXChemistry::scale_inc= 0.001;
amrex::Real BMXChemistry::max_fusion_separation= 0.0;

int BMXChemistry::p_num_reals = 0;
int BMXChemistry::p_num_ints = 0;
std::vector<amrex::Real> BMXChemistry::p_initial_concentrations;

BMXChemistry *BMXChemistry::p_instance = NULL;

/**
 * Retrieve instance of BMXChemistry object
 */
BMXChemistry* BMXChemistry::instance()
{
  if (p_instance == NULL) {
    p_instance = new BMXChemistry();
  }
  return p_instance;
}

/**
 * Constructor
 */
BMXChemistry::BMXChemistry()
{
  p_num_species = NUM_PARTICLE_CHEM_COMPONENTS;
  p_num_ivals = 0;
  p_num_reals = 3*p_num_species;
  p_num_ints = 0;
  p_inc_offset = 2*p_num_species;
  p_verbose = false;
  p_int_vals.push_back(p_num_species);
  p_int_vals.push_back(p_num_ivals);
  p_int_vals.push_back(p_num_reals);
  p_int_vals.push_back(p_num_ints);
  p_int_vals.push_back(p_inc_offset);
}

/**
 * Destructor
 */
BMXChemistry::~BMXChemistry()
{
  delete p_instance;
}

/**
 * Set values of particle integer data
 * @param ipar pointer to internal integer values for each particle
 */
void BMXChemistry::setIntegers(int *ipar)
{
  ipar[0] = p_num_species;
  ipar[1] = p_num_ivals;
  ipar[2] = p_num_reals;
  ipar[3] = p_num_ints;
  ipar[4] = p_inc_offset;
}

/**
 * Setup chemistry model by reading a parameter file (a file is not currently
 * being used but probably will be at some point).
 * @param file name of parameter file used by chemistry model
 */
void BMXChemistry::setParams(const char* /*file*/)
{
  ParmParse pp("chem_species");

  std::string layout_error;
  const auto layout_mode =
      BMXChemLayout::classifyMeshSpecies(FLUID::chem_species, &layout_error);
  if (layout_mode == BMXChemLayout::MeshMode::invalid) {
    amrex::Abort("P09 chemistry layout invalid: " + layout_error);
  }

  p_initial_concentrations.assign(NUM_PARTICLE_CHEM_COMPONENTS, 0.0);
  if (layout_mode == BMXChemLayout::MeshMode::disabled) {
    for (int n = 0; n < BMXChemLayout::disabled_mesh_components; ++n) {
      p_initial_concentrations[n] = FLUID::init_conc[n];
    }
  } else if (layout_mode == BMXChemLayout::MeshMode::enabled) {
    // Carbon slots retain their existing mesh-bound initialization. The three
    // internal phosphorus values have distinct ownership and therefore require
    // an explicit input; no biological initialization is defaulted here.
    for (int n = 0; n < BMXChemLayout::P_D; ++n) {
      p_initial_concentrations[n] = FLUID::init_conc[n];
    }
    std::vector<Real> initial_particle_p;
    pp.getarr("initial_particle_P", initial_particle_p);
    if (initial_particle_p.size() != 3) {
      amrex::Abort("chem_species.initial_particle_P must contain exactly "
                   "P_D P_E P_F for the enabled P09 layout");
    }
    p_initial_concentrations[BMXChemLayout::P_D] = initial_particle_p[0];
    p_initial_concentrations[BMXChemLayout::P_E] = initial_particle_p[1];
    p_initial_concentrations[BMXChemLayout::P_F] = initial_particle_p[2];
  } else {
    const int count = amrex::min(
        static_cast<int>(FLUID::init_conc.size()),
        NUM_PARTICLE_CHEM_COMPONENTS);
    for (int n = 0; n < count; ++n) {
      p_initial_concentrations[n] = FLUID::init_conc[n];
    }
  }

  pp.get("k1",k1);
  pp.get("kr1",kr1);
  pp.get("k2",k2);
  pp.get("kr2",kr2);
  pp.get("k3",k3);
  pp.get("kr3",kr3);
  pp.get("k4",k4);
  pp.get("kr4",kr4);
  pp.get("k5",k5);
  pp.get("kr5",kr5);
  pp.get("k6",k6);
  pp.get("kr6",kr6);
  pp.get("k7",k7);
  pp.get("kr7",kr7);
  kP = k1;
  krP = kr1;
  pp.query("kP",kP);
  pp.query("krP",krP);
  pp.get("kg",kg);
  pp.get("kv",kv);
  pp.get("kb",kb);
  pp.get("kbv",kbv);
  p_growth_limit = 0.0;
  pp.query("p_growth_limit",p_growth_limit);
  qP = 0.0;
  pp.query("qP",qP);
  if (p_growth_limit != 0.0 && qP <= 0.0) {
    amrex::Abort("chem_species.qP must be positive when p_growth_limit is enabled");
  }
  mtA = 0.0;
  pp.query("mass_transfer_A",mtA);
  mtB = 0.0;
  pp.query("mass_transfer_B",mtB);
  mtC = 0.0;
  pp.query("mass_transfer_C",mtC);
  mtP = mtA;
  pp.query("mass_transfer_P",mtP);
  if (layout_mode == BMXChemLayout::MeshMode::enabled &&
      (kP != 0.0 || krP != 0.0 || mtP != 0.0 ||
       p_growth_limit != 0.0)) {
    amrex::Abort("enabled P09 plumbing requires chem_species.kP, "
                 "chem_species.krP, chem_species.mass_transfer_P, and "
                 "chem_species.p_growth_limit to be exactly zero; C07 does "
                 "not activate later phosphorus operators");
  }
  fusion_prob = 0.0;
  pp.query("fusion_probability",fusion_prob);
  max_fusion_separation = 5.0e-4;
  pp.query("max_fusion_separation",max_fusion_separation);
  p_overlap = 0.2;
  scale_inc = 0.001;
  pp.query("bond_scaling_increment",scale_inc);

  /* figure out cutoff for neighbor list */
  Real vol = SPECIES::max_vol;
  radius_max = SPECIES::max_rad;
  length_max = SPECIES::max_len;
  Real radius = pow((3.0*vol/(4.0*M_PI)),1.0/3.0);
  ParmParse ppF("cell_force");
  Real width;
  ppF.get("neighbor_width",width);
  // TODO: Come up with correct neighborhood value base on what types of cells
  //       are being simulated
  width = 1.1*(2.0*radius+width);
  DEM::neighborhood = width*width;
  ParmParse ppV("bmx");
  int verbose = 0;
  ppV.query("verbose",verbose);
  if (verbose != 0) {
    p_verbose = true;
  } else {
    p_verbose = false;
  }

}

/**
 * Return the number of Real and int variables
 * @param num_ints number of integer variables in cell model
 * @param num_reals number of Real variables in cell model
 * @param tot_ints total number of ints needed by BMXChemistry (may include
 *        utility data)
 * @param tot_reals total number of Reals needed by BMXChemistry (may include
 *        utility data)
 */
void BMXChemistry::getVarArraySizes(int *num_ints, int *num_reals, int *tot_ints, int *tot_reals)
{
  *num_reals = p_num_species;
  *num_ints = p_num_ivals;
  *tot_reals = p_num_reals;
  *tot_ints = p_num_ints;
}

/**
 * Print concentrations of chemical species in cell
 * @param id particle index
 * @param p_vals values of concentrations in particles
 * @param p_par values of particle parameters
 */
void BMXChemistry::printCellConcentrations(int id, Real *p_vals, Real *p_par)
{
  if (p_verbose) {
    const auto layout_mode =
        BMXChemLayout::classifyMeshSpecies(FLUID::chem_species);
    const int print_count =
        layout_mode == BMXChemLayout::MeshMode::enabled
            ? NUM_PARTICLE_CHEM_COMPONENTS
            : amrex::min(static_cast<int>(FLUID::chem_species.size()),
                         NUM_PARTICLE_CHEM_COMPONENTS);
    printf("\n");
    printf("        Particle: %d\n",id);
    for (int n = 0; n < print_count; ++n) {
      const char* prefix = (p_vals[n] < 0.0) ? " XXXX  " : "       ";
      printf("%s Concentration %s: %18.6e\n", prefix,
             BMXChemLayout::particleName(layout_mode, n), p_vals[n]);
    }
    printf("        Cell volume    : %18.6e\n",p_par[realIdx::vol]);
   // printf("        X velocity     : %18.6e\n",p_par[realIdx::velx]);
   // printf("        Y velocity     : %18.6e\n",p_par[realIdx::vely]);
   // printf("        Z velocity     : %18.6e\n",p_par[realIdx::velz]);
  }
}

const std::vector<Real>& BMXChemistry::getParticleInitialConcentrations() const
{
  return p_initial_concentrations;
}

/**
 * Return values that are also stored in particle idata fields
 * @param idx intIdx parameter representing index of desired value
 * @return integer value at index location
 */
int BMXChemistry::getIntData(int idx)
{
  return p_int_vals[idx];
}

/**
 * Return a vector containing all chemical paramters needed to integrate
 * chemistry
 * @param chempar vector of parameters used in chemistry
 */
void BMXChemistry::getChemParams(amrex::Gpu::DeviceVector<Real> &chempar)
{
  chempar.clear();
  chempar.push_back(k1);
  chempar.push_back(k2);
  chempar.push_back(k3);
  chempar.push_back(k4);
  chempar.push_back(k5);                  // 5
  chempar.push_back(k6);
  chempar.push_back(k7);
  chempar.push_back(kr1);
  chempar.push_back(kr2);
  chempar.push_back(kr3);                 // 10
  chempar.push_back(kr4);
  chempar.push_back(kr5);
  chempar.push_back(kr6);
  chempar.push_back(kr7);
  chempar.push_back(kg);                  // 15
  chempar.push_back(kv);
  chempar.push_back(kb);
  chempar.push_back(kbv);
  chempar.push_back(bacteria_radius_max);
  chempar.push_back(radius_max);          // 19
  chempar.push_back(length_max);          // 20
  chempar.push_back(kP);                  // 21
  chempar.push_back(krP);                 // 22
  chempar.push_back(p_growth_limit);      // 23
  chempar.push_back(qP);                  // 24
}

/** Returen a vector containing exchange parameters
 * @return vector of exchange parameters
 */
amrex::Gpu::DeviceVector<Real> BMXChemistry::getExchangeParameters()
{
  amrex::Gpu::DeviceVector<Real> ret(NUM_PARTICLE_CHEM_COMPONENTS, 0.0);
  ret[0] = mtA;
  ret[1] = mtB;
  ret[2] = mtC;
  ret[P_COMP] = mtP;
  return ret;
}

/**
 * Return a vector containing parameters for segment fusion
 * @return vector of fusion parameters
 */
amrex::Gpu::DeviceVector<Real> BMXChemistry::getFusionParameters()
{
  amrex::Gpu::DeviceVector<Real> ret;
  ret.push_back(fusion_prob);
  ret.push_back(max_fusion_separation);
  ret.push_back(scale_inc);
  return ret;
}
