#include <bmx_chem_layout.H>

#include <cassert>
#include <iostream>
#include <string>
#include <vector>

int main()
{
  using BMXChemLayout::MeshMode;

  const std::vector<std::string> disabled =
      {"A", "B", "C", "D", "F", "P"};
  const std::vector<std::string> enabled =
      {"A", "B", "C", "D", "F", "P_D", "P_F"};

  std::string error;
  assert(BMXChemLayout::classifyMeshSpecies(disabled, &error) ==
         MeshMode::disabled);
  assert(BMXChemLayout::classifyMeshSpecies(enabled, &error) ==
         MeshMode::enabled);

  for (int n = 0; n < BMXChemLayout::disabled_mesh_components; ++n) {
    assert(BMXChemLayout::meshToParticle(n, MeshMode::disabled) == n);
    assert(BMXChemLayout::particleToMesh(n, MeshMode::disabled) == n);
  }
  assert(BMXChemLayout::particleToMesh(BMXChemLayout::P_E,
                                       MeshMode::disabled) == -1);
  assert(BMXChemLayout::particleToMesh(BMXChemLayout::P_F,
                                       MeshMode::disabled) == -1);

  for (int n = 0; n < 6; ++n) {
    assert(BMXChemLayout::meshToParticle(n, MeshMode::enabled) == n);
    assert(BMXChemLayout::particleToMesh(n, MeshMode::enabled) == n);
  }
  assert(BMXChemLayout::meshToParticle(6, MeshMode::enabled) ==
         BMXChemLayout::P_F);
  assert(BMXChemLayout::particleToMesh(BMXChemLayout::P_E,
                                       MeshMode::enabled) == -1);
  assert(BMXChemLayout::particleToMesh(BMXChemLayout::P_F,
                                       MeshMode::enabled) == 6);

  const std::vector<std::vector<std::string>> invalid = {
      {"A", "B", "C", "D", "F", "P", "P_D", "P_F"},
      {"A", "B", "C", "D", "F", "P_D", "P_E", "P_F"},
      {"A", "B", "C", "D", "F", "P_D"},
      {"A", "B", "C", "F", "D", "P_D", "P_F"},
      {"A", "B", "C", "D", "F", "P_uptake", "P_F"}
  };
  for (const auto& names : invalid) {
    error.clear();
    assert(BMXChemLayout::classifyMeshSpecies(names, &error) ==
           MeshMode::invalid);
    assert(!error.empty());
  }

  assert(std::string(BMXChemLayout::particleName(MeshMode::enabled, 5)) ==
         "P_D");
  assert(std::string(BMXChemLayout::particleName(MeshMode::enabled, 6)) ==
         "P_E");
  assert(std::string(BMXChemLayout::particleName(MeshMode::enabled, 7)) ==
         "P_F");
  assert(BMXChemLayout::particle_components == 8);
  assert(BMXChemLayout::max_mesh_components == 7);
  assert(BMXChemLayout::checkpoint_schema_minimum == 2);
  assert(std::string(BMXChemLayout::layout_hash_sha256).size() == 64);
  assert(std::string(BMXChemLayout::decision_contract_sha256).size() == 64);
  assert(!BMXChemLayout::checkpoint_schema_ready);

  std::cout << "C07 layout unit PASS\n";
  return 0;
}
