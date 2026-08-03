//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#ifndef BMX_CHEM_LAYOUT_H_
#define BMX_CHEM_LAYOUT_H_

#include <string>
#include <vector>

namespace BMXChemLayout
{
  constexpr int disabled_mesh_components = 6;
  constexpr int enabled_mesh_components = 7;
  constexpr int max_mesh_components = enabled_mesh_components;
  constexpr int particle_components = 8;
  constexpr int particle_blocks = 3;

  constexpr int checkpoint_schema_minimum = 2;
  constexpr const char* layout_id = "bmx-p09-three-state-layout-v2";
  constexpr const char* layout_descriptor =
      "mesh-disabled:A,B,C,D,F,P;"
      "mesh-enabled:A,B,C,D,F,P_D,P_F;"
      "particle:A,B,C,D,F,P_D,P_E,P_F;"
      "maps-disabled:0>0,1>1,2>2,3>3,4>4,5>5;"
      "maps-enabled:0>0,1>1,2>2,3>3,4>4,5>5,6>7";
  constexpr const char* units_contract_id =
      "MD-5b43f4b235dec87e-06+MD-5b43f4b235dec87e-07";
  constexpr const char* decision_contract_id =
      "P09-U01+P09-U02+P09-U03+UDC-20260801-P10-U01+"
      "UDC-20260801-MENTOR-DECISION-FREEZE-V2+UDC-20260801-P13-V1+"
      "UDC-20260802-P14-C12-BINDINGS-V1";
  constexpr const char* layout_hash_sha256 =
      "522cb38eacea08c97093860e26b34973b0b0e945545aef54adbd032946d8d669";
  constexpr const char* decision_contract_sha256 =
      "34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066";
  constexpr const char* units_decision_source_sha256 =
      "6d8581062e25cfec2c2b4b6630d98278a7473687d512443f6fed64fde8068271";

  // C08 writer freeze. Independent review is still required before any final
  // run, but checkpoint compatibility must bind the exact writer-frozen bytes
  // rather than an unversioned or outcome-dependent order.
  constexpr const char* operator_order_id = "bmx-p10-global-order-v1";
  constexpr const char* operator_order_contract_sha256 =
      "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6";
  constexpr const char* topology_event_contract_id =
      "bmx-p10-topology-event-v1";
  constexpr const char* topology_event_contract_sha256 =
      "a6a5a8a8d299ee3e0cfc30f6d359d84ed13fb9872db7cf51bfb38777b800bdfb";
  constexpr const char* global_ledger_schema_id =
      "bmx-p10-global-ledger-v1";
  constexpr const char* global_ledger_schema_sha256 =
      "23b0593ae3c07fbe6c20a4994226f2dce0f81af60a53b4ba91d3fa0f26c5a95b";
  constexpr bool checkpoint_schema_ready = true;

  enum class MeshMode
  {
    unmanaged,
    disabled,
    enabled,
    invalid
  };

  enum ParticleComponent
  {
    A = 0,
    B = 1,
    C = 2,
    D = 3,
    F = 4,
    P_D = 5,
    P_E = 6,
    P_F = 7
  };

  inline bool contains(const std::vector<std::string>& names,
                       const std::string& wanted)
  {
    for (const auto& name : names) {
      if (name == wanted) return true;
    }
    return false;
  }

  inline bool equals(const std::vector<std::string>& names,
                     const char* const* expected, int count)
  {
    if (static_cast<int>(names.size()) != count) return false;
    for (int n = 0; n < count; ++n) {
      if (names[n] != expected[n]) return false;
    }
    return true;
  }

  inline MeshMode classifyMeshSpecies(const std::vector<std::string>& names,
                                      std::string* error = nullptr)
  {
    static const char* const disabled_names[disabled_mesh_components] =
        {"A", "B", "C", "D", "F", "P"};
    static const char* const enabled_names[enabled_mesh_components] =
        {"A", "B", "C", "D", "F", "P_D", "P_F"};

    if (equals(names, disabled_names, disabled_mesh_components)) {
      return MeshMode::disabled;
    }
    if (equals(names, enabled_names, enabled_mesh_components)) {
      return MeshMode::enabled;
    }

    const bool has_p = contains(names, "P");
    const bool has_pd = contains(names, "P_D");
    const bool has_pe = contains(names, "P_E");
    const bool has_pf = contains(names, "P_F");
    const bool has_alias = contains(names, "P_uptake") ||
                           contains(names, "P_growth") ||
                           contains(names, "P_delivery");

    if (!(has_p || has_pd || has_pe || has_pf || has_alias)) {
      return MeshMode::unmanaged;
    }

    if (error != nullptr) {
      if (has_alias) {
        *error = "legacy P_uptake/P_growth/P_delivery aliases are not allowed";
      } else if (has_pe) {
        *error = "P_E is internal-only and cannot appear in fluid.chem_species";
      } else if (has_p && has_pd) {
        *error = "fluid.chem_species cannot contain both P and P_D";
      } else if (has_pd && !has_pf) {
        *error = "enabled P_D layout requires mesh P_F";
      } else if (has_pf && !has_pd) {
        *error = "mesh P_F is valid only in the enabled P_D layout";
      } else {
        *error = "phosphorus layout must be exactly disabled A B C D F P or "
                 "enabled A B C D F P_D P_F";
      }
    }
    return MeshMode::invalid;
  }

  inline const char* modeName(MeshMode mode)
  {
    switch (mode) {
      case MeshMode::disabled: return "disabled";
      case MeshMode::enabled: return "enabled";
      case MeshMode::unmanaged: return "unmanaged";
      default: return "invalid";
    }
  }

  inline int meshToParticle(int mesh_component, MeshMode mode)
  {
    if (mode == MeshMode::enabled && mesh_component == 6) return P_F;
    return mesh_component;
  }

  inline int particleToMesh(int particle_component, MeshMode mode)
  {
    if (mode == MeshMode::enabled) {
      if (particle_component == P_E) return -1;
      if (particle_component == P_F) return 6;
    }
    if (mode == MeshMode::disabled && particle_component >= 6) return -1;
    return particle_component;
  }

  inline const char* particleName(MeshMode mode, int component)
  {
    static const char* const enabled_names[particle_components] =
        {"A", "B", "C", "D", "F", "P_D", "P_E", "P_F"};
    static const char* const disabled_names[particle_components] =
        {"A", "B", "C", "D", "F", "P", "reserved_P_E", "reserved_P_F"};

    if (component < 0 || component >= particle_components) return "invalid";
    return mode == MeshMode::enabled ? enabled_names[component]
                                     : disabled_names[component];
  }
}

#endif
