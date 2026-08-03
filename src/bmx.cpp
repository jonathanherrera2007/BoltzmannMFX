//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include <bmx.H>

#include <iomanip>

#include <AMReX_BC_TYPES.H>
#include <AMReX_Box.H>

#include <bmx_chem.H>          // realIdx, NUM_CHEM_COMPONENTS, MAX_CHEM_REAL_VAR
#include <bmx_fluid_parms.H>
#include <bmx_chem_species_parms.H>
#include <bmx_pc_phosphorus.H>

std::string      bmx::particle_init_type   = "AsciiFile";
std::string      bmx::load_balance_type    = "KnapSack";
std::string      bmx::knapsack_weight_type = "RunTimeCosts";
int              bmx::load_balance_fluid   = 1;
int              bmx::knapsack_nmax        = 128;
DepositionScheme bmx::m_cnc_deposition_scheme;
DepositionScheme bmx::m_vf_deposition_scheme;
amrex::Real      bmx::m_deposition_scale_factor = 1.0;

int  bmx::plot_int        = -1;
Real bmx::plot_per_approx = -1.;
Real bmx::plot_per_exact  = -1.;
int  bmx::print_sums      = 0;   // diagnostic, off by default

// Destructor
bmx::~bmx ()
{
  if (DEM::solve)
    delete pc;

  for (int lev(0); lev <= finest_level; ++lev)
  {
    // Face-based coefficients b in MAC projection and implicit diffusion solve
    delete bcoeff[lev][0];
    delete bcoeff[lev][1];
    delete bcoeff[lev][2];

    // Boundary conditions types
    delete bc_ilo[lev];
    delete bc_ihi[lev];
    delete bc_jlo[lev];
    delete bc_jhi[lev];
    delete bc_klo[lev];
    delete bc_khi[lev];
  }

  // used if load_balance_type == "KnapSack"
  for (int lev = 0; lev < particle_cost.size(); ++lev)
    delete particle_cost[lev];

  for (int lev = 0; lev < fluid_cost.size(); ++lev)
    delete fluid_cost[lev];
} 

// Constructor
bmx::bmx ()
{
    // NOTE: Geometry on all levels has just been defined in the AmrCore
    // constructor. No valid BoxArray and DistributionMapping have been defined.
    // But the arrays for them have been resized.

    SetNProper(2);

    /****************************************************************************
     *                                                                          *
     * Initialize time steps                                                    *
     *                                                                          *
     ***************************************************************************/

    t_old.resize(max_level+1,-1.e100);
    t_new.resize(max_level+1,0.0);


    /****************************************************************************
     *                                                                          *
     * Initialize boundary conditions (used by fill-patch)                      *
     *                                                                          *
     ***************************************************************************/

    bcs_X.resize(0); // X_k
    bcs_D.resize(0); // D_k

    //___________________________________________________________________________
    // Boundary conditions used for level-sets

    // walls (Neumann)
    int bc_lo[] = {FOEXTRAP, FOEXTRAP, FOEXTRAP};
    int bc_hi[] = {FOEXTRAP, FOEXTRAP, FOEXTRAP};

    for (int idim = 0; idim < AMREX_SPACEDIM; ++idim) {
        // lo-side BCs
        if (bc_lo[idim] == BCType::int_dir  ||  // periodic uses "internal Dirichlet"
            bc_lo[idim] == BCType::foextrap ||  // first-order extrapolation
            bc_lo[idim] == BCType::ext_dir ) {  // external Dirichlet
        }
        else {
            amrex::Abort("Invalid level-set bc_lo");
        }

        // hi-side BCSs
        if (bc_hi[idim] == BCType::int_dir  ||  // periodic uses "internal Dirichlet"
            bc_hi[idim] == BCType::foextrap ||  // first-order extrapolation
            bc_hi[idim] == BCType::ext_dir ) {  // external Dirichlet
        }
        else {
            amrex::Abort("Invalid level-set bc_hi");
        }
    }

    m_X_k_bc_types["Dirichlet"] = {bc_list.get_minf()};

    fine_mask = 0;

    Gpu::synchronize();
}

// Conservation / content diagnostic.
//
// DIAGNOSTIC ONLY. This function reads state and prints; it must never modify
// fluid or particle data. It is the fluid-side observable that the particle
// ASCII dump cannot provide (the dump carries no mesh values), and P10 needs it
// for conservation.
//
// It was previously dead -- an unconditional `return;` on entry -- and while
// dead it acquired two defects that would have produced confident nonsense the
// moment anyone re-enabled it:
//
//   1. Particle content was read at components 22/23/24 as A/B/C. Those were
//      correct only when realIdx::first_data was 22. It is now 28, so those
//      indices actually read dvdt, tau_split and bond_scale. Fixed by deriving
//      the offsets from realIdx::first_data rather than hard-coding them.
//   2. Mesh components were hard-coded as 0/1/2. The mesh order comes from the
//      `fluid.chem_species` input, so a reordered input would have silently
//      mislabelled every printed sum. Fixed by resolving each name against
//      FLUID::chem_species and aborting if the expected species is absent.
//
// Gating: off by default via `bmx.print_sums`. With the flag unset this returns
// before touching anything, so default behaviour -- and every piece of evidence
// already captured -- is bit-for-bit unchanged.
void
bmx::ComputeAndPrintSums()
{
    if (!print_sums) return;

    BL_PROFILE("bmx::ComputeAndPrintSums()");

    // Resolve mesh component indices by NAME from the authoritative list.
    // Hard-coded indices are what broke this function before.
    auto mesh_comp = [] (const std::string& want) -> int {
        for (int i = 0; i < FLUID::nchem_species; ++i)
            if (FLUID::chem_species[i] == want) return i;
        amrex::Abort("ComputeAndPrintSums: fluid species '" + want +
                     "' is not present in fluid.chem_species; the conservation "
                     "diagnostic cannot report a species it cannot locate.");
        return -1;
    };

    const int iA = mesh_comp("A");
    const int iB = mesh_comp("B");
    const int iC = mesh_comp("C");

    // Particle chemistry lives in the p_vals block that begins at
    // realIdx::first_data; the committed sub-block is the first
    // NUM_CHEM_COMPONENTS entries (see bmx_chem_K.H, "Now update the actual
    // particle values").
    //
    // The particle block and the mesh list agree for A/B/C but DIVERGE at slot
    // 4: the kernel calls it cE while `fluid.chem_species` calls it F. That
    // disagreement is tracked as D-C07-01. This diagnostic therefore reports
    // only A/B/C, and asserts the agreement it relies on instead of trusting
    // it -- if the layouts ever separate at slots 0-2, this aborts rather than
    // summing two different quantities into one number.
    if (iA != 0 || iB != 1 || iC != 2)
        amrex::Abort("ComputeAndPrintSums: fluid.chem_species does not start "
                     "with A B C, so the mesh order no longer matches the "
                     "particle committed block. Refusing to report sums that "
                     "would pair different species together.");

    const int pA = realIdx::first_data + 0;
    const int pB = realIdx::first_data + 1;
    const int pC = realIdx::first_data + 2;

    static_assert(realIdx::first_data + NUM_CHEM_COMPONENTS <= MAX_CHEM_REAL_VAR,
                  "committed chemistry block does not fit in the particle real "
                  "storage; realIdx::first_data or NUM_CHEM_COMPONENTS changed");

    const auto p_lo = Geom(0).ProbLoArray();
    const auto p_hi = Geom(0).ProbHiArray();

    Real domain_vol = (p_hi[2]-p_lo[2])*(p_hi[1]-p_lo[1])*(p_hi[0]-p_lo[0]);

    Real fluid_vol = volSum();

    Real particle_vol = pc->computeParticleVolume();

    Real A_in_fluid     = volWgtSum(get_X_k_const(), iA);
    Real A_in_particles = pc->computeParticleContent(pA);

    Real B_in_fluid     = volWgtSum(get_X_k_const(), iB);
    Real B_in_particles = pc->computeParticleContent(pB);

    Real C_in_fluid     = volWgtSum(get_X_k_const(), iC);
    Real C_in_particles = pc->computeParticleContent(pC);

    // Volume closure is REPORTED, not enforced.
    //
    // The dead version aborted here on a 1e-12 relative mismatch. That
    // assertion had never run: enabling it kills the fungi case within ~20
    // steps, because volSum() tracks the deposited volume-fraction field while
    // computeParticleVolume() sums the particles' own geometry, and the two
    // separate as segments grow (observed: particle volume 5.89e-10 -> 6.89e-10
    // with the residual crossing the tolerance).
    //
    // A read-only diagnostic must not terminate a run -- aborting is itself a
    // behavioural change, and a far larger one than the drift it is reporting.
    // So the residual is emitted as data. Whether that drift is acceptable is a
    // conservation question for P10, and it is recorded as a finding rather
    // than hidden by removing the check or widened away by loosening it.
    const Real vol_residual = domain_vol - (fluid_vol + particle_vol);
    const Real vol_rel = (domain_vol != 0.0) ? std::abs(vol_residual) / domain_vol : 0.0;

    // Every line this function emits is prefixed "SUMS" so a harness can strip
    // the diagnostic wholesale when comparing trajectories, without maintaining
    // a list of prose fragments.
    amrex::Print() << "SUMS component_map A mesh=" << iA << " particle=" << pA << "\n"
                   << "SUMS component_map B mesh=" << iB << " particle=" << pB << "\n"
                   << "SUMS component_map C mesh=" << iC << " particle=" << pC << "\n"
                   << "SUMS first_data " << realIdx::first_data << "\n";

    amrex::Print() << std::setprecision(17)
                   << "SUMS domain_volume "   << domain_vol   << "\n"
                   << "SUMS fluid_volume "    << fluid_vol    << "\n"
                   << "SUMS particle_volume " << particle_vol << "\n"
                   << "SUMS volume_residual " << vol_residual << "\n"
                   << "SUMS volume_residual_rel " << vol_rel  << "\n"
                   << "SUMS A_fluid "     << A_in_fluid     << "\n"
                   << "SUMS A_particles " << A_in_particles << "\n"
                   << "SUMS B_fluid "     << B_in_fluid     << "\n"
                   << "SUMS B_particles " << B_in_particles << "\n"
                   << "SUMS C_fluid "     << C_in_fluid     << "\n"
                   << "SUMS C_particles " << C_in_particles << "\n"
                   << "SUMS A_total " << A_in_fluid + A_in_particles << "\n"
                   << "SUMS C_total " << C_in_fluid + C_in_particles << "\n";
}

bool
bmx::P10Enabled () const
{
    return BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) ==
           BMXChemLayout::MeshMode::enabled;
}

void
bmx::AuditP10Ledger (const char* boundary, bool require_bound)
{
    if (!P10Enabled()) return;
    if (!FLUID::solve || !DEM::solve || !advect_fluid_chem_species ||
        pc == nullptr) {
      amrex::Abort(
          "P10 enabled mode requires coupled fluid chemistry and particles at every ledger boundary");
    }

    auto mesh_component = [] (const char* wanted) -> int {
      for (int component = 0; component < FLUID::nchem_species; ++component) {
        if (FLUID::chem_species[component] == wanted) return component;
      }
      amrex::Abort(std::string("P10 ledger cannot locate mesh component ") +
                   wanted);
      return -1;
    };

    BMXPhosphorus::ParticleTotals mesh;
    mesh.d = volWgtSum(get_X_k_const(), mesh_component("P_D"));
    mesh.e = 0.0;
    mesh.f = volWgtSum(get_X_k_const(), mesh_component("P_F"));
    BMXPhosphorus::requireAuditBuffersEmpty(*pc, boundary);
    const auto internal = BMXPhosphorus::computeInternalAmounts(*pc);
    if (!BMXPhosphorus::cumulativeLedger().reference_bound && require_bound) {
      if (p10_restart_metadata_expected) {
        amrex::Abort(
            "P10 restarted checkpoint reached an audit with an unbound reference");
      }
      BMXPhosphorus::validateBondTopology(*pc);
      BMXPhosphorus::resetCumulativeLedger();
      BMXPhosphorus::bindReferenceTotal(mesh, internal);
    }
    const auto snapshot = BMXPhosphorus::evaluateGlobalLedger(
        mesh, internal, require_bound);
    const auto& cumulative = BMXPhosphorus::cumulativeLedger();

    amrex::Print() << std::setprecision(17)
                   << "P10_LEDGER boundary=" << boundary
                   << " reference_bound=" << cumulative.reference_bound
                   << " reference_total=" << cumulative.reference_total_p
                   << " mesh_D=" << mesh.d
                   << " mesh_F=" << mesh.f
                   << " internal_D=" << internal.d
                   << " internal_E=" << internal.e
                   << " internal_F=" << internal.f
                   << " accounted=" << snapshot.accounted_total_p
                   << " residual=" << snapshot.residual
                   << " tolerance=" << snapshot.tolerance << "\n";
}

void
bmx::compute_grad_X(int lev, Real time, MultiFab& gradx_X_k, MultiFab& grady_X_k, MultiFab& gradz_X_k) 
{
    fillpatch_Xk(get_X_k(), time);

    auto const dxInv = geom[lev].InvCellSizeArray();
 
    MultiFab* X_k = get_X_k()[lev];
    for (MFIter mfi(*X_k,TilingIfNotGPU()); mfi.isValid(); ++mfi)
    {
        Box const& bx = mfi.tilebox();

        const Array4<const Real>  X_k_arr = X_k->const_array(mfi);
        const Array4<      Real> gx_k_arr = gradx_X_k.array(mfi);
        const Array4<      Real> gy_k_arr = grady_X_k.array(mfi);
        const Array4<      Real> gz_k_arr = gradz_X_k.array(mfi);

        ParallelFor(bx, FLUID::nchem_species, [=]
          AMREX_GPU_DEVICE (int i, int j, int k, int n) noexcept
          {
              gx_k_arr(i,j,k,n) = (X_k_arr(i+1,j,k,n) - X_k_arr(i-1,j,k,n)) * 0.5 * dxInv[0];
              gy_k_arr(i,j,k,n) = (X_k_arr(i,j+1,k,n) - X_k_arr(i,j-1,k,n)) * 0.5 * dxInv[1];
              gz_k_arr(i,j,k,n) = (X_k_arr(i,j,k+1,n) - X_k_arr(i,j,k-1,n)) * 0.5 * dxInv[2];
          });
    }
}

void
bmx::avgDown (int crse_lev, const MultiFab& S_fine, MultiFab& S_crse)
{
    BL_PROFILE("bmx::avgDown()");

    average_down(S_fine, S_crse, 0, S_fine.nComp(), refRatio(crse_lev));
}

Vector< MultiFab* > bmx::get_X_k () noexcept
{
  Vector<MultiFab*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->X_k);
  }
  return r;
}

Vector< MultiFab* > bmx::get_X_k_old () noexcept
{
  Vector<MultiFab*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->X_ko);
  }
  return r;
}

Vector< MultiFab* > bmx::get_D_k () noexcept
{
  Vector<MultiFab*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->D_k);
  }
  return r;
}

Vector< MultiFab* > bmx::get_vf_old () noexcept
{
  Vector<MultiFab*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->vf_o);
  }
  return r;
}

Vector< MultiFab* > bmx::get_vf_new () noexcept
{
  Vector<MultiFab*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->vf_n);
  }
  return r;
}

Vector< MultiFab* > bmx::get_X_rhs () noexcept
{
  Vector<MultiFab*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->X_rhs);
  }
  return r;
}

Vector< MultiFab const*> bmx::get_X_k_const () const noexcept
{
  Vector<MultiFab const*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->X_k);
  }
  return r;
}

Vector< MultiFab const*> bmx::get_X_k_old_const () const noexcept
{
  Vector<MultiFab const*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->X_ko);
  }
  return r;
}

Vector< MultiFab const*> bmx::get_D_k_const () const noexcept
{
  Vector<MultiFab const*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->D_k);
  }
  return r;
}

Vector< MultiFab const*> bmx::get_vf_old_const () const noexcept
{
  Vector<MultiFab const*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->vf_o);
  }
  return r;
}

Vector< MultiFab const*> bmx::get_vf_new_const () const noexcept
{
  Vector<MultiFab const*> r;
  r.reserve(m_leveldata.size());
  for (int lev = 0; lev < m_leveldata.size(); ++lev) {
    r.push_back(m_leveldata[lev]->vf_n);
  }
  return r;
}
