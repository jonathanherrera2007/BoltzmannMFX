//
// C12/P14 final-topology O09 interface export transaction.
//
#include <bmx_pc.H>

#include <bmx_fluid_parms.H>
#include <bmx_phosphorus_export_K.H>
#include <bmx_phosphorus_geometry_K.H>

#include <AMReX_GpuContainers.H>

#include <cstdint>
#include <string>

void BMXParticleContainer::ApplyP14Export (int update_id, amrex::Real dt)
{
  const auto& binding = BMXPhosphorusExport::config();
  if (!binding.enabled) return;
  BMXPhosphorusExport::requireUpdateAvailable(update_id);

  BMXPhosphorusExport::StepResult local;
  std::uint64_t particles_evaluated = 0;
  std::uint64_t eligible_particles = 0;
  std::uint64_t true_crossings = 0;
  std::uint64_t solid_contacts = 0;
  std::uint64_t accepted_export_events = 0;
  std::uint64_t donor_capped_events = 0;
  std::uint64_t roundoff_clamps = 0;

  // Each final owned AoS entry is visited once. The transaction deliberately
  // has no mesh-cell, AMR, tile, rank, or decomposition input.
  for (int lev = 0; lev <= finest_level; ++lev) {
    const auto geometry = BMXPhosphorusGeometry::loadAndValidate(
        Geom(lev), FLUID::chem_species);
    for (BMXParIter pti(*this, lev); pti.isValid(); ++pti) {
      PairIndex index(pti.index(), pti.LocalTileIndex());
      auto& tile = GetParticles(lev)[index];
      auto& aos = tile.GetArrayOfStructs();
      ParticleType* particles = aos().dataPtr();
      const int owned_count = tile.numRealParticles();
      amrex::Gpu::DeviceScalar<BMXPhosphorusExport::DeviceAccumulator>
          accumulator_gpu(BMXPhosphorusExport::DeviceAccumulator{});
      auto* accumulator = accumulator_gpu.dataPtr();
      amrex::ParallelFor(
          owned_count,
          [particles,dt,k_export=binding.k_export,geometry,accumulator]
          AMREX_GPU_DEVICE (int particle_index) noexcept
          {
            auto& particle = particles[particle_index];
            const amrex::Real position[3] = {
                particle.pos(0), particle.pos(1), particle.pos(2)};
            const auto step = BMXPhosphorusExport::apply(
                position, &particle.rdata(0), &particle.idata(0), dt,
                k_export, geometry);
            BMXPhosphorusExport::accumulate(step, accumulator);
          });
      amrex::Gpu::synchronize();
      const auto step = accumulator_gpu.dataValue();
      local.interface_fraction += step.interface_fraction_sum;
      local.active_volume += step.active_volume;
      local.active_d_basis += step.active_d_basis;
      local.requested_p += step.requested_p;
      local.accepted_p += step.accepted_p;
      local.rejected_p += step.rejected_p;
      local.exported_p += step.exported_p;
      local.reward_a += step.reward_a;
      if (step.maximum_status > static_cast<int>(local.status)) {
        local.status = static_cast<BMXPhosphorusExport::StepStatus>(
            step.maximum_status);
      }
      particles_evaluated += static_cast<std::uint64_t>(
          step.particles_evaluated);
      eligible_particles += static_cast<std::uint64_t>(
          step.eligible_particles);
      true_crossings += static_cast<std::uint64_t>(step.true_crossings);
      solid_contacts += static_cast<std::uint64_t>(step.solid_contacts);
      accepted_export_events += static_cast<std::uint64_t>(
          step.accepted_export_events);
      donor_capped_events += static_cast<std::uint64_t>(
          step.donor_capped_events);
      roundoff_clamps += static_cast<std::uint64_t>(step.roundoff_clamps);
    }
  }
  BMXPhosphorusExport::recordStep(
      update_id, local, particles_evaluated, eligible_particles,
      true_crossings, solid_contacts, accepted_export_events,
      donor_capped_events, roundoff_clamps);
}
