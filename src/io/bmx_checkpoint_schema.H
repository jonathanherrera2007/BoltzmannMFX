//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#ifndef BMX_CHECKPOINT_SCHEMA_H_
#define BMX_CHECKPOINT_SCHEMA_H_

#include <bmx_chem_layout.H>

#include <AMReX_Geometry.H>
#include <AMReX_REAL.H>

#include <array>
#include <iosfwd>
#include <string>
#include <vector>

namespace BMXCheckpointSchema
{
  constexpr int version = 8;
  constexpr const char* version_line = "Checkpoint version: 8";

  struct GeometryMetadata
  {
    int enabled = 0;
    int schema = 0;
    std::string contract_id = "DISABLED";
    std::string contract_sha256 = "DISABLED";
    std::string stage = "DISABLED";
    std::array<amrex::Real, AMREX_SPACEDIM> prob_lo{};
    std::array<amrex::Real, AMREX_SPACEDIM> prob_hi{};
    std::array<int, AMREX_SPACEDIM> periodic{};
  };

  void validateVersionLine (const std::string& line);

  void writeMetadata (
      std::ostream& stream,
      BMXChemLayout::MeshMode mode,
      const std::vector<std::string>& mesh_names,
      const amrex::Geometry& geometry);

  GeometryMetadata readValidateAndRestoreMetadata (
      std::istream& stream,
      BMXChemLayout::MeshMode expected_mode,
      const std::vector<std::string>& expected_mesh_names,
      const amrex::Geometry& runtime_geometry);

  void validateGeometryLines (
      const GeometryMetadata& metadata,
      const amrex::Real* prob_lo,
      const amrex::Real* prob_hi);
}

#endif
