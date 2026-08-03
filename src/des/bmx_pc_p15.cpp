//
// C13/P15 canonical metric-graph terminal areas and conservative O07 bonded-D
// finite-volume transport.  This is deliberately separate from the frozen
// legacy chemistry kernel and its evaluateExchange path.
//
#include <bmx_pc.H>

#include <bmx_fluid_parms.H>
#include <bmx_p15_stage0_K.H>
#include <bmx_pc_phosphorus.H>
#include <bmx_phosphorus_geometry_K.H>
#include <bmx_phosphorus_uptake_K.H>

#include <AMReX_GpuContainers.H>
#include <AMReX_ParallelDescriptor.H>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iterator>
#include <limits>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

namespace
{
  using amrex::Real;

  struct SegmentKey
  {
    int id = -1;
    int cpu = -1;
  };

  bool operator< (const SegmentKey& first, const SegmentKey& second)
  {
    return first.id < second.id ||
           (first.id == second.id && first.cpu < second.cpu);
  }

  bool operator== (const SegmentKey& first, const SegmentKey& second)
  {
    return first.id == second.id && first.cpu == second.cpu;
  }

  struct PortKey
  {
    SegmentKey segment;
    int site = 0;
  };

  bool operator< (const PortKey& first, const PortKey& second)
  {
    return first.segment < second.segment ||
           (first.segment == second.segment && first.site < second.site);
  }

  struct HostSegment
  {
    int id = -1;
    int cpu = -1;
    int amrex_id = -1;
    int amrex_cpu = -1;
    int cell_type = -1;
    int position = -1;
    int bond_count = 0;
    int endpoint_id[4] = {-1, -1, -1, -1};
    int endpoint_cpu[4] = {-1, -1, -1, -1};
    int endpoint_site[4] = {-1, -1, -1, -1};
    Real center[3] = {0.0, 0.0, 0.0};
    Real radius = 0.0;
    Real length = 0.0;
    Real theta = 0.0;
    Real phi = 0.0;
    Real stored_area = 0.0;
    Real volume = 0.0;
    Real d_amount = 0.0;
  };

  static_assert(std::is_trivially_copyable<HostSegment>::value,
                "P15 MPI graph records must be trivially copyable");

  struct DisjointSet
  {
    explicit DisjointSet (std::size_t count)
      : parent(count), rank(count, 0)
    {
      for (std::size_t index = 0; index < count; ++index) {
        parent[index] = static_cast<int>(index);
      }
    }

    int find (int value)
    {
      int root = value;
      while (parent[root] != root) root = parent[root];
      while (parent[value] != value) {
        const int next = parent[value];
        parent[value] = root;
        value = next;
      }
      return root;
    }

    void unite (int first, int second)
    {
      first = find(first);
      second = find(second);
      if (first == second) return;
      if (rank[first] < rank[second]) std::swap(first, second);
      parent[second] = first;
      if (rank[first] == rank[second]) ++rank[first];
    }

    std::vector<int> parent;
    std::vector<int> rank;
  };

  struct Junction
  {
    PortKey key;
    std::vector<int> ports;
  };

  struct CanonicalGraph
  {
    std::vector<HostSegment> segments;
    std::map<SegmentKey,int> segment_index;
    std::vector<Junction> junctions;
    std::vector<int> port_junction;
    std::vector<std::array<bool,2>> bonded_site;
  };

  struct VirtualPair
  {
    int first_segment = -1;
    int second_segment = -1;
    Real conductance = 0.0;
  };

  amrex::Gpu::DeviceVector<BMXP15Stage0::TerminalAreaRecord>
      terminal_area_device;

  [[noreturn]] void graphAbort (const std::string& reason)
  {
    amrex::Abort("P15_CANONICAL_GRAPH_INVALID: " + reason);
  }

  bool finite (Real value) { return BMXP15Stage0::finite(value); }

  std::vector<HostSegment> gatherSegments (
      const BMXParticleContainer& particles)
  {
    std::vector<HostSegment> local;
    for (int level = 0; level <= particles.finestLevel(); ++level) {
      const auto& level_particles = particles.GetParticles(level);
      for (const auto& entry : level_particles) {
        const auto& tile = entry.second;
        const int count = tile.numRealParticles();
        const auto& aos = tile.GetArrayOfStructs();
        amrex::Gpu::HostVector<BMXParticleContainer::ParticleType> host(count);
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         aos.begin(), aos.begin() + count, host.begin());
        for (const auto& particle : host) {
          HostSegment record{};
          record.id = particle.idata(intIdx::id);
          record.cpu = particle.idata(intIdx::cpu);
          record.amrex_id = static_cast<int>(particle.id());
          record.amrex_cpu = particle.cpu();
          record.cell_type = particle.idata(intIdx::cell_type);
          record.position = particle.idata(intIdx::position);
          record.bond_count = particle.idata(intIdx::n_bnds);
          for (int bond = 0; bond < 4; ++bond) {
            record.endpoint_id[bond] =
                particle.idata(intIdx::seg1_id1 + bond);
            record.endpoint_cpu[bond] =
                particle.idata(intIdx::seg1_id2 + bond);
            record.endpoint_site[bond] =
                particle.idata(intIdx::site1 + bond);
          }
          for (int direction = 0; direction < 3; ++direction) {
            record.center[direction] = particle.pos(direction);
          }
          record.radius = particle.rdata(realIdx::radius);
          record.length = particle.rdata(realIdx::c_length);
          record.theta = particle.rdata(realIdx::theta);
          record.phi = particle.rdata(realIdx::phi);
          record.stored_area = particle.rdata(realIdx::area);
          record.volume = particle.rdata(realIdx::vol);
          const Real concentration = particle.rdata(
              realIdx::first_data + BMXChemLayout::P_D);
          record.d_amount = concentration * record.volume;
          local.push_back(record);
        }
      }
    }

    std::vector<HostSegment> all;
#ifdef AMREX_USE_MPI
    if (local.size() > static_cast<std::size_t>(
            std::numeric_limits<int>::max()/sizeof(HostSegment))) {
      graphAbort("local MPI graph payload exceeds INT_MAX bytes");
    }
    const int local_bytes = static_cast<int>(
        local.size() * sizeof(HostSegment));
    std::vector<int> byte_counts(amrex::ParallelDescriptor::NProcs());
    MPI_Allgather(&local_bytes, 1, MPI_INT, byte_counts.data(), 1, MPI_INT,
                  amrex::ParallelDescriptor::Communicator());
    std::vector<int> byte_offsets(byte_counts.size(), 0);
    int total_bytes = 0;
    for (std::size_t rank = 0; rank < byte_counts.size(); ++rank) {
      if (byte_counts[rank] < 0 ||
          byte_counts[rank] % static_cast<int>(sizeof(HostSegment)) != 0 ||
          total_bytes > std::numeric_limits<int>::max() -
                            byte_counts[rank]) {
        graphAbort("invalid or overflowing MPI graph payload");
      }
      byte_offsets[rank] = total_bytes;
      total_bytes += byte_counts[rank];
    }
    all.resize(static_cast<std::size_t>(total_bytes) / sizeof(HostSegment));
    MPI_Allgatherv(local.empty() ? nullptr : local.data(),
                   local_bytes, MPI_BYTE,
                   all.empty() ? nullptr : all.data(),
                   byte_counts.data(), byte_offsets.data(), MPI_BYTE,
                   amrex::ParallelDescriptor::Communicator());
#else
    all = local;
#endif
    std::sort(all.begin(), all.end(),
        [] (const HostSegment& first, const HostSegment& second)
        {
          return SegmentKey{first.id, first.cpu} <
                 SegmentKey{second.id, second.cpu};
        });
    return all;
  }

  int portIndex (int segment_index, int site)
  {
    return 2*segment_index + (site-1);
  }

  PortKey portKey (const std::vector<HostSegment>& segments, int port)
  {
    const int segment = port/2;
    return {{segments[segment].id, segments[segment].cpu}, port%2 + 1};
  }

  Real areaTolerance (Real first, Real second)
  {
    Real scale = 1.0;
    scale = std::max(scale, std::abs(first));
    scale = std::max(scale, std::abs(second));
    return 64.0 * std::numeric_limits<double>::epsilon() * scale;
  }

  CanonicalGraph buildGraph (const BMXParticleContainer& particles)
  {
    CanonicalGraph graph;
    graph.segments = gatherSegments(particles);
    graph.bonded_site.resize(graph.segments.size(), {false, false});
    DisjointSet sets(2*graph.segments.size());

    for (std::size_t index = 0; index < graph.segments.size(); ++index) {
      const auto& segment = graph.segments[index];
      const SegmentKey key{segment.id, segment.cpu};
      if (segment.id < 0 || segment.cpu < 0 ||
          segment.id != segment.amrex_id || segment.cpu != segment.amrex_cpu ||
          !graph.segment_index.emplace(key, static_cast<int>(index)).second) {
        graphAbort("inconsistent or duplicate particle identity");
      }
      if (segment.bond_count < 0 || segment.bond_count > 4) {
        graphAbort("bond count is outside [0,4]");
      }
      const Real geometry_values[] = {
          segment.center[0], segment.center[1], segment.center[2],
          segment.radius, segment.length, segment.theta, segment.phi,
          segment.stored_area, segment.volume, segment.d_amount};
      for (const Real value : geometry_values) {
        if (!finite(value)) graphAbort("nonfinite segment state");
      }
      if (segment.cell_type == cellType::FUNGI) {
        if (!(segment.radius > 0.0) || !(segment.length > 0.0) ||
            !(segment.volume > 0.0) || segment.stored_area < 0.0) {
          graphAbort("nonpositive fungal geometry or owning volume");
        }
        for (int site = 1; site <= 2; ++site) {
          for (int direction = 0; direction < 3; ++direction) {
            const Real endpoint = BMXP15Stage0::endpointCoordinate(
                segment.center[direction], segment.length,
                segment.theta, segment.phi, site, direction);
            if (!finite(endpoint)) {
              graphAbort("nonfinite endpoint geometry");
            }
          }
        }
      } else if (segment.bond_count != 0) {
        graphAbort("a nonfungal particle carries a segment bond");
      }
    }

    for (std::size_t owner_index = 0;
         owner_index < graph.segments.size(); ++owner_index) {
      const auto& owner = graph.segments[owner_index];
      std::set<SegmentKey> seen_neighbors;
      for (int bond = 0; bond < owner.bond_count; ++bond) {
        const int site = owner.endpoint_site[bond];
        if (site != 1 && site != 2) {
          graphAbort("invalid endpoint site");
        }
        const SegmentKey neighbor_key{
            owner.endpoint_id[bond], owner.endpoint_cpu[bond]};
        if (neighbor_key == SegmentKey{owner.id, owner.cpu}) {
          graphAbort("self bond is not a distinct reciprocal endpoint record");
        }
        if (!seen_neighbors.insert(neighbor_key).second) {
          graphAbort("duplicate or disagreeing bond record");
        }
        const auto neighbor_entry = graph.segment_index.find(neighbor_key);
        if (neighbor_entry == graph.segment_index.end()) {
          graphAbort("missing bonded particle");
        }
        const int neighbor_index = neighbor_entry->second;
        const auto& neighbor = graph.segments[neighbor_index];
        int reciprocal_count = 0;
        int reciprocal_site = -1;
        for (int candidate = 0;
             candidate < neighbor.bond_count; ++candidate) {
          if (neighbor.endpoint_id[candidate] == owner.id &&
              neighbor.endpoint_cpu[candidate] == owner.cpu) {
            ++reciprocal_count;
            reciprocal_site = neighbor.endpoint_site[candidate];
          }
        }
        if (reciprocal_count != 1) {
          graphAbort("missing or duplicate reciprocal bond");
        }
        if (reciprocal_site != 1 && reciprocal_site != 2) {
          graphAbort("disagreeing reciprocal site metadata");
        }
        graph.bonded_site[owner_index][site-1] = true;
        graph.bonded_site[neighbor_index][reciprocal_site-1] = true;
        sets.unite(portIndex(static_cast<int>(owner_index), site),
                   portIndex(neighbor_index, reciprocal_site));
      }
    }

    std::map<int,std::vector<int>> root_ports;
    for (int port = 0;
         port < static_cast<int>(2*graph.segments.size()); ++port) {
      root_ports[sets.find(port)].push_back(port);
    }
    graph.junctions.reserve(root_ports.size());
    for (auto& entry : root_ports) {
      auto& ports = entry.second;
      std::sort(ports.begin(), ports.end(),
          [&graph] (int first, int second)
          {
            return portKey(graph.segments, first) <
                   portKey(graph.segments, second);
          });
      graph.junctions.push_back({portKey(graph.segments, ports.front()),
                                 std::move(ports)});
    }
    std::sort(graph.junctions.begin(), graph.junctions.end(),
        [] (const Junction& first, const Junction& second)
        {
          return first.key < second.key;
        });
    graph.port_junction.resize(2*graph.segments.size(), -1);
    for (std::size_t junction = 0;
         junction < graph.junctions.size(); ++junction) {
      for (const int port : graph.junctions[junction].ports) {
        if (graph.port_junction[port] != -1) {
          graphAbort("port appears in multiple junctions");
        }
        graph.port_junction[port] = static_cast<int>(junction);
      }
    }
    return graph;
  }

  struct TerminalResult
  {
    std::vector<BMXP15Stage0::TerminalAreaRecord> records;
    Real full_sum = 0.0;
    Real tip005_sum = 0.0;
    Real tip010_sum = 0.0;
    Real tip020_sum = 0.0;
    std::uint64_t segment_count = 0;
    std::uint64_t origin_count = 0;
  };

  bool endpointInside (Real distance, Real length, Real threshold)
  {
    if (!finite(distance)) return false;
    const Real tolerance = BMXP15Stage0::terminalSnapTolerance(
        distance, distance, length, threshold);
    if (std::abs(distance-threshold) <= tolerance) distance = threshold;
    return distance <= threshold;
  }

  TerminalResult computeTerminalAreas (const CanonicalGraph& graph)
  {
    const Real infinity = std::numeric_limits<Real>::infinity();
    std::vector<std::vector<std::pair<int,Real>>> adjacency(
        graph.junctions.size());
    for (std::size_t segment_index = 0;
         segment_index < graph.segments.size(); ++segment_index) {
      const auto& segment = graph.segments[segment_index];
      if (segment.cell_type != cellType::FUNGI) continue;
      const int first = graph.port_junction[2*segment_index];
      const int second = graph.port_junction[2*segment_index+1];
      if (first < 0 || second < 0) graphAbort("missing metric-graph endpoint");
      adjacency[first].push_back({second, segment.length});
      adjacency[second].push_back({first, segment.length});
    }
    for (auto& edges : adjacency) {
      std::sort(edges.begin(), edges.end(),
          [] (const auto& first, const auto& second)
          {
            if (first.first != second.first) return first.first < second.first;
            return first.second < second.second;
          });
    }

    std::set<int> source_nodes;
    for (std::size_t segment_index = 0;
         segment_index < graph.segments.size(); ++segment_index) {
      const auto& segment = graph.segments[segment_index];
      if (segment.cell_type != cellType::FUNGI ||
          segment.position != siteLocation::TIP) continue;
      const bool first_bonded = graph.bonded_site[segment_index][0];
      const bool second_bonded = graph.bonded_site[segment_index][1];
      if (first_bonded && second_bonded) {
        graphAbort("AMBIGUOUS_TIP_ORIENTATION");
      }
      if (!first_bonded) {
        source_nodes.insert(graph.port_junction[2*segment_index]);
      }
      if (!second_bonded) {
        source_nodes.insert(graph.port_junction[2*segment_index+1]);
      }
    }

    std::vector<Real> distance(graph.junctions.size(), infinity);
    using QueueEntry = std::pair<Real,int>;
    std::priority_queue<QueueEntry,
                        std::vector<QueueEntry>,
                        std::greater<QueueEntry>> queue;
    for (const int source : source_nodes) {
      distance[source] = 0.0;
      queue.push({0.0, source});
    }
    while (!queue.empty()) {
      const auto current = queue.top();
      queue.pop();
      if (current.first != distance[current.second]) continue;
      for (const auto& edge : adjacency[current.second]) {
        const Real candidate = current.first + edge.second;
        if (!finite(candidate)) graphAbort("nonfinite graph distance");
        if (candidate < distance[edge.first]) {
          distance[edge.first] = candidate;
          queue.push({candidate, edge.first});
        }
      }
    }

    TerminalResult result;
    result.records.reserve(graph.segments.size());
    result.origin_count = static_cast<std::uint64_t>(source_nodes.size());
    constexpr Real thresholds[3] = {0.005, 0.010, 0.020};
    for (std::size_t segment_index = 0;
         segment_index < graph.segments.size(); ++segment_index) {
      const auto& segment = graph.segments[segment_index];
      BMXP15Stage0::TerminalAreaRecord record;
      record.particle_id = segment.id;
      record.cpu_id = segment.cpu;
      if (segment.cell_type == cellType::FUNGI) {
        ++result.segment_count;
        const bool first_free = !graph.bonded_site[segment_index][0];
        const bool second_free = !graph.bonded_site[segment_index][1];
        const int free_caps = static_cast<int>(first_free) +
                              static_cast<int>(second_free);
        record.full_area = BMXP15Stage0::physicalArea(
            segment.radius, segment.length, free_caps);
        if (!finite(record.full_area) || record.full_area < 0.0 ||
            std::abs(record.full_area-segment.stored_area) >
                areaTolerance(record.full_area, segment.stored_area)) {
          std::ostringstream message;
          message.precision(17);
          message << "stored/computed full-area mismatch for segment "
                  << segment.id << ',' << segment.cpu
                  << ": stored=" << segment.stored_area
                  << " computed=" << record.full_area
                  << " tolerance="
                  << areaTolerance(record.full_area, segment.stored_area);
          graphAbort(message.str());
        }
        const Real first_distance =
            distance[graph.port_junction[2*segment_index]];
        const Real second_distance =
            distance[graph.port_junction[2*segment_index+1]];
        Real* areas[3] = {&record.tip_005_area,
                          &record.tip_010_area,
                          &record.tip_020_area};
        for (int threshold_index = 0; threshold_index < 3;
             ++threshold_index) {
          const Real threshold = thresholds[threshold_index];
          const Real eligible_length =
              BMXP15Stage0::terminalEligibleLength(
                  first_distance, second_distance, segment.length,
                  threshold);
          const int eligible_caps =
              static_cast<int>(first_free && endpointInside(
                  first_distance, segment.length, threshold)) +
              static_cast<int>(second_free && endpointInside(
                  second_distance, segment.length, threshold));
          *areas[threshold_index] = BMXP15Stage0::physicalArea(
              segment.radius, eligible_length, eligible_caps);
          if (!finite(*areas[threshold_index]) ||
              *areas[threshold_index] < 0.0) {
            graphAbort("nonfinite terminal-zone area");
          }
        }
        if (record.tip_005_area > record.tip_010_area ||
            record.tip_010_area > record.tip_020_area ||
            record.tip_020_area > record.full_area) {
          graphAbort("terminal-zone areas are not nested inside full area");
        }
        result.full_sum += record.full_area;
        result.tip005_sum += record.tip_005_area;
        result.tip010_sum += record.tip_010_area;
        result.tip020_sum += record.tip_020_area;
      }
      result.records.push_back(record);
    }
    const Real sums[] = {result.full_sum, result.tip005_sum,
                         result.tip010_sum, result.tip020_sum};
    for (const Real value : sums) {
      if (!finite(value) || value < 0.0) {
        graphAbort("nonfinite canonical terminal-area sum");
      }
    }
    return result;
  }

  Real selectedArea (const BMXP15Stage0::TerminalAreaRecord& record,
                     BMXPhosphorusUptake::AreaMode mode,
                     Real multiplier)
  {
    using Mode = BMXPhosphorusUptake::AreaMode;
    switch (mode) {
    case Mode::full_exposed_surface:
      return record.full_area;
    case Mode::zero:
      return 0.0;
    case Mode::tip_005:
      return record.tip_005_area;
    case Mode::tip_010:
      return record.tip_010_area;
    case Mode::tip_020:
      return record.tip_020_area;
    case Mode::tip_010_area_matched:
      return multiplier * record.tip_010_area;
    }
    graphAbort("unknown uptake-area mode");
  }

  std::vector<VirtualPair> buildVirtualPairs (
      const CanonicalGraph& graph,
      Real diffusivity,
      Real& maximum_diagonal_rate,
      std::vector<Real>& rate_sum)
  {
    std::vector<VirtualPair> pairs;
    rate_sum.assign(graph.segments.size(), 0.0);
    maximum_diagonal_rate = 0.0;
    for (const auto& junction : graph.junctions) {
      if (junction.ports.size() < 2) continue;
      std::vector<Real> half(junction.ports.size(), 0.0);
      Real junction_sum = 0.0;
      for (std::size_t index = 0; index < junction.ports.size(); ++index) {
        const int segment_index = junction.ports[index]/2;
        const auto& segment = graph.segments[segment_index];
        half[index] = BMXP15Stage0::halfSegmentConductance(
            diffusivity, segment.radius, segment.length);
        if (!finite(half[index]) || !(half[index] > 0.0)) {
          graphAbort("nonfinite or nonpositive port half-segment conductance");
        }
        junction_sum += half[index];
      }
      if (!finite(junction_sum) || !(junction_sum > 0.0)) {
        graphAbort("nonfinite or nonpositive junction conductance sum");
      }
      for (std::size_t first = 0; first < junction.ports.size(); ++first) {
        for (std::size_t second = first+1;
             second < junction.ports.size(); ++second) {
          const int first_segment = junction.ports[first]/2;
          const int second_segment = junction.ports[second]/2;
          if (first_segment == second_segment) continue;
          const Real conductance = BMXP15Stage0::virtualPairConductance(
              half[first], half[second], junction_sum);
          if (!finite(conductance) || !(conductance > 0.0)) {
            graphAbort("nonfinite or nonpositive virtual-pair conductance");
          }
          pairs.push_back({first_segment, second_segment, conductance});
          rate_sum[first_segment] += conductance;
          rate_sum[second_segment] += conductance;
        }
      }
    }
    for (std::size_t segment = 0; segment < graph.segments.size(); ++segment) {
      if (graph.segments[segment].cell_type != cellType::FUNGI) continue;
      const Real diagonal_rate = rate_sum[segment] /
                                 graph.segments[segment].volume;
      if (!finite(diagonal_rate) || diagonal_rate < 0.0) {
        graphAbort("nonfinite or negative finite-volume diagonal rate");
      }
      maximum_diagonal_rate = std::max(maximum_diagonal_rate, diagonal_rate);
    }
    return pairs;
  }

  void commitDAmounts (BMXParticleContainer& particles,
                       const CanonicalGraph& graph,
                       const std::vector<Real>& amounts)
  {
    for (int level = 0; level <= particles.finestLevel(); ++level) {
      auto& level_particles = particles.GetParticles(level);
      for (auto& entry : level_particles) {
        auto& tile = entry.second;
        const int count = tile.numRealParticles();
        auto& aos = tile.GetArrayOfStructs();
        amrex::Gpu::HostVector<BMXParticleContainer::ParticleType> host(count);
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         aos.begin(), aos.begin()+count, host.begin());
        for (auto& particle : host) {
          const SegmentKey key{particle.idata(intIdx::id),
                               particle.idata(intIdx::cpu)};
          const auto found = graph.segment_index.find(key);
          if (found == graph.segment_index.end()) {
            graphAbort("local particle is absent from canonical global graph");
          }
          const int index = found->second;
          if (graph.segments[index].cell_type != cellType::FUNGI) continue;
          const Real volume = particle.rdata(realIdx::vol);
          if (volume != graph.segments[index].volume || !(volume > 0.0)) {
            graphAbort("owning volume changed inside fixed O07 transaction");
          }
          const Real concentration = amounts[index]/volume;
          if (!finite(concentration) || concentration < 0.0) {
            graphAbort("invalid D concentration at O07 commit");
          }
          particle.rdata(realIdx::first_data + BMXChemLayout::P_D) =
              concentration;
        }
        amrex::Gpu::copy(amrex::Gpu::hostToDevice,
                         host.begin(), host.end(), aos.begin());
      }
    }
    amrex::Gpu::synchronize();
  }
}

namespace BMXP15Stage0
{
  void initializeCanonicalBonds (BMXParticleContainer& particles)
  {
    if (!enabled()) return;
    auto segments = gatherSegments(particles);
    struct InitialBond
    {
      int neighbor = -1;
      int own_site = 0;
      int neighbor_site = 0;
    };
    std::vector<std::vector<InitialBond>> bonds(segments.size());
    constexpr Real inherited_endpoint_tolerance = 1.0e-7;
    constexpr Real tolerance_squared =
        inherited_endpoint_tolerance*inherited_endpoint_tolerance;

    auto endpoint = [&segments] (std::size_t segment,
                                 int site,
                                 int direction)
    {
      return endpointCoordinate(
          segments[segment].center[direction], segments[segment].length,
          segments[segment].theta, segments[segment].phi, site, direction);
    };

    std::set<SegmentKey> identities;
    for (const auto& segment : segments) {
      if (segment.id < 0 || segment.cpu < 0 ||
          segment.id != segment.amrex_id ||
          segment.cpu != segment.amrex_cpu ||
          !identities.insert({segment.id, segment.cpu}).second) {
        graphAbort("initial network has an inconsistent particle identity");
      }
      if (segment.bond_count != 0) {
        graphAbort(
            "fresh P15 ASCII initialization must not contain pre-existing bonds");
      }
      if (segment.cell_type == cellType::FUNGI &&
          (!(segment.radius > 0.0) || !(segment.length > 0.0) ||
           !(segment.volume > 0.0) || !finite(segment.radius) ||
           !finite(segment.length) || !finite(segment.volume) ||
           !finite(segment.theta) || !finite(segment.phi))) {
        graphAbort("initial fungal geometry is nonfinite or nonpositive");
      }
    }

    for (std::size_t first = 0; first < segments.size(); ++first) {
      if (segments[first].cell_type != cellType::FUNGI) continue;
      for (std::size_t second = first+1; second < segments.size(); ++second) {
        if (segments[second].cell_type != cellType::FUNGI) continue;
        int matching_first_site = 0;
        int matching_second_site = 0;
        int match_count = 0;
        for (int first_site = 1; first_site <= 2; ++first_site) {
          for (int second_site = 1; second_site <= 2; ++second_site) {
            Real distance_squared = 0.0;
            for (int direction = 0; direction < 3; ++direction) {
              const Real difference = endpoint(first, first_site, direction) -
                                      endpoint(second, second_site, direction);
              distance_squared += difference*difference;
            }
            if (!finite(distance_squared)) {
              graphAbort("initial endpoint comparison is nonfinite");
            }
            if (distance_squared < tolerance_squared) {
              matching_first_site = first_site;
              matching_second_site = second_site;
              ++match_count;
            }
          }
        }
        if (match_count > 1) {
          graphAbort("initial segment pair has ambiguous coincident endpoints");
        }
        if (match_count == 1) {
          bonds[first].push_back({static_cast<int>(second),
                                  matching_first_site,
                                  matching_second_site});
          bonds[second].push_back({static_cast<int>(first),
                                   matching_second_site,
                                   matching_first_site});
        }
      }
    }

    for (std::size_t segment = 0; segment < bonds.size(); ++segment) {
      auto& entries = bonds[segment];
      std::sort(entries.begin(), entries.end(),
          [&segments] (const InitialBond& first,
                       const InitialBond& second)
          {
            const SegmentKey first_key{segments[first.neighbor].id,
                                       segments[first.neighbor].cpu};
            const SegmentKey second_key{segments[second.neighbor].id,
                                        segments[second.neighbor].cpu};
            if (first_key < second_key) return true;
            if (second_key < first_key) return false;
            if (first.own_site != second.own_site) {
              return first.own_site < second.own_site;
            }
            return first.neighbor_site < second.neighbor_site;
          });
      if (entries.size() > 4) {
        graphAbort("initial canonical bond degree exceeds inherited capacity four");
      }
    }

    for (int level = 0; level <= particles.finestLevel(); ++level) {
      auto& level_particles = particles.GetParticles(level);
      for (auto& entry : level_particles) {
        auto& tile = entry.second;
        const int count = tile.numRealParticles();
        auto& aos = tile.GetArrayOfStructs();
        amrex::Gpu::HostVector<BMXParticleContainer::ParticleType> host(count);
        amrex::Gpu::copy(amrex::Gpu::deviceToHost,
                         aos.begin(), aos.begin()+count, host.begin());
        for (auto& particle : host) {
          const SegmentKey key{particle.idata(intIdx::id),
                               particle.idata(intIdx::cpu)};
          const auto found = std::lower_bound(
              segments.begin(), segments.end(), key,
              [] (const HostSegment& candidate, const SegmentKey& wanted)
              {
                return SegmentKey{candidate.id, candidate.cpu} < wanted;
              });
          if (found == segments.end() ||
              !(SegmentKey{found->id, found->cpu} == key)) {
            graphAbort("local initial particle is absent from canonical network");
          }
          const std::size_t index = static_cast<std::size_t>(
              std::distance(segments.begin(), found));
          if (found->cell_type != cellType::FUNGI) continue;
          const auto& entries = bonds[index];
          particle.idata(intIdx::n_bnds) =
              static_cast<int>(entries.size());
          for (int bond = 0; bond < 4; ++bond) {
            particle.idata(intIdx::seg1_id1 + bond) = 0;
            particle.idata(intIdx::seg1_id2 + bond) = 0;
            particle.idata(intIdx::site1 + bond) = 0;
          }
          bool first_site = false;
          bool second_site = false;
          for (std::size_t bond = 0; bond < entries.size(); ++bond) {
            const auto& connection = entries[bond];
            const auto& neighbor = segments[connection.neighbor];
            particle.idata(intIdx::seg1_id1 + static_cast<int>(bond)) =
                neighbor.id;
            particle.idata(intIdx::seg1_id2 + static_cast<int>(bond)) =
                neighbor.cpu;
            particle.idata(intIdx::site1 + static_cast<int>(bond)) =
                connection.own_site;
            first_site = first_site || connection.own_site == 1;
            second_site = second_site || connection.own_site == 2;
          }
          particle.idata(intIdx::position) =
              first_site && second_site ? siteLocation::INTERIOR
                                        : siteLocation::TIP;
        }
        amrex::Gpu::copy(amrex::Gpu::hostToDevice,
                         host.begin(), host.end(), aos.begin());
      }
    }
    amrex::Gpu::synchronize();
    std::uint64_t records = 0;
    for (const auto& entries : bonds) records += entries.size();
    amrex::Print() << "P15_INITIAL_NETWORK canonical_segments="
                   << segments.size() << " canonical_bond_records="
                   << records
                   << " endpoint_tolerance="
                   << inherited_endpoint_tolerance << '\n';
  }

  void prepareTerminalAreas (BMXParticleContainer& particles)
  {
    if (!enabled()) return;
    const auto graph = buildGraph(particles);
    auto terminal = computeTerminalAreas(graph);
    const auto& uptake = BMXPhosphorusUptake::config();
    if (!uptake.enabled) {
      graphAbort("P15 Stage 0 requires P12 uptake enabled");
    }
    const bool area_matched =
        uptake.area_mode ==
            BMXPhosphorusUptake::AreaMode::tip_010_area_matched;
    Real multiplier = uptake.area_multiplier;
    if (area_matched) {
      const auto& binding = config();
      if (!(terminal.full_sum > 0.0) || !(terminal.tip010_sum > 0.0)) {
        graphAbort("area-matched initial network has nonpositive area operand");
      }
      if (!areaMatchState().bound) {
        AreaMatchState state;
        state.bound = 1;
        state.initial_full_area = terminal.full_sum;
        state.initial_tip010_area = terminal.tip010_sum;
        state.multiplier = state.initial_full_area /
                           state.initial_tip010_area;
        if (state.multiplier != binding.expected_area_match_multiplier ||
            state.initial_full_area != binding.expected_initial_full_area ||
            state.initial_tip010_area !=
                binding.expected_initial_tip010_area ||
            uptake.area_multiplier != state.multiplier) {
          graphAbort(
              "derived initial area-match fields differ from the hash-bound case configuration");
        }
        bindAreaMatch(state);
      } else {
        const auto& state = areaMatchState();
        if (state.multiplier != config().expected_area_match_multiplier ||
            state.initial_full_area != config().expected_initial_full_area ||
            state.initial_tip010_area !=
                config().expected_initial_tip010_area ||
            uptake.area_multiplier != state.multiplier) {
          graphAbort("restart area-match fields differ from runtime configuration");
        }
      }
      multiplier = areaMatchState().multiplier;
    } else {
      if (uptake.area_multiplier != 1.0 ||
          config().expected_area_match_multiplier != 0.0 ||
          config().expected_initial_full_area != 0.0 ||
          config().expected_initial_tip010_area != 0.0) {
        graphAbort("non-area-matched P15 case contains area-match state");
      }
      if (areaMatchState().bound) {
        graphAbort("non-area-matched restart contains a bound area multiplier");
      }
      multiplier = 1.0;
    }

    Real effective_sum = 0.0;
    for (const auto& record : terminal.records) {
      effective_sum += selectedArea(record, uptake.area_mode, multiplier);
    }
    if (!finite(effective_sum) || effective_sum < 0.0) {
      graphAbort("nonfinite effective uptake-area sum");
    }

    terminal_area_device.resize(terminal.records.size());
    amrex::Gpu::copy(amrex::Gpu::hostToDevice,
                     terminal.records.begin(), terminal.records.end(),
                     terminal_area_device.begin());
    amrex::Gpu::synchronize();
    recordTerminalSnapshot(
        terminal.full_sum, terminal.tip005_sum, terminal.tip010_sum,
        terminal.tip020_sum, effective_sum, terminal.segment_count,
        terminal.origin_count);
  }

  const TerminalAreaRecord* terminalAreaDeviceData ()
  {
    return terminal_area_device.empty() ? nullptr :
           terminal_area_device.data();
  }

  int terminalAreaRecordCount ()
  {
    if (terminal_area_device.size() > static_cast<std::size_t>(
            std::numeric_limits<int>::max())) {
      graphAbort("terminal-area record count exceeds INT_MAX");
    }
    return static_cast<int>(terminal_area_device.size());
  }

  void applyBondedDTransport (BMXParticleContainer& particles,
                              Real outer_dt)
  {
    const auto& binding = config();
    if (!binding.enabled || binding.bonded_d_diffusivity == 0.0) {
      // The D_bond=0 contract is an exact identity: do not build junctions,
      // evaluate formulas, write particle bytes, or touch transport ledgers.
      return;
    }
    if (!finite(outer_dt) || !(outer_dt > 0.0)) {
      graphAbort("nonfinite or nonpositive outer timestep");
    }
    const auto before = BMXPhosphorus::computeInternalAmounts(particles);
    const auto graph = buildGraph(particles);
    Real maximum_diagonal_rate = 0.0;
    std::vector<Real> rate_sum;
    const auto pairs = buildVirtualPairs(
        graph, binding.bonded_d_diffusivity,
        maximum_diagonal_rate, rate_sum);
    if (!finite(maximum_diagonal_rate) || maximum_diagonal_rate < 0.0) {
      graphAbort("invalid global maximum diagonal rate");
    }
    const Real raw_substeps = outer_dt*maximum_diagonal_rate/0.25;
    if (!finite(raw_substeps) ||
        raw_substeps > static_cast<Real>(std::numeric_limits<int>::max()-1)) {
      graphAbort("bonded-D stability substep count overflows int");
    }
    int substeps = stableSubsteps(outer_dt, maximum_diagonal_rate);
    if (binding.cap_fault_injection) substeps = 1;
    const Real dt = outer_dt/static_cast<Real>(substeps);
    if (!finite(dt) || !(dt > 0.0) ||
        (!binding.cap_fault_injection &&
         dt*maximum_diagonal_rate > 0.25)) {
      graphAbort("bonded-D explicit stability verification failed");
    }

    std::vector<Real> amounts(graph.segments.size(), 0.0);
    for (std::size_t segment = 0; segment < graph.segments.size(); ++segment) {
      amounts[segment] = graph.segments[segment].d_amount;
      const Real tolerance = BMXPhosphorus::localTolerance(
          std::abs(amounts[segment]));
      if (!finite(amounts[segment]) || amounts[segment] < -tolerance) {
        graphAbort("negative D amount beyond the frozen numerical tolerance");
      }
      if (amounts[segment] < 0.0) amounts[segment] = 0.0;
    }

    BondedStep ledger;
    ledger.maximum_diagonal_rate = maximum_diagonal_rate;
    ledger.minimum_donor_scale = 1.0;
    ledger.internal_substeps = static_cast<std::uint64_t>(substeps);
    ledger.virtual_pairs = static_cast<std::uint64_t>(pairs.size());
    const Real binary64_epsilon =
        2.220446049250313080847263336181640625e-16;
    for (int substep = 0; substep < substeps; ++substep) {
      const std::vector<Real> snapshot = amounts;
      std::vector<Real> concentration(snapshot.size(), 0.0);
      std::vector<Real> outgoing(snapshot.size(), 0.0);
      std::vector<Real> local_min(snapshot.size(), 0.0);
      std::vector<Real> local_max(snapshot.size(), 0.0);
      for (std::size_t segment = 0; segment < snapshot.size(); ++segment) {
        if (graph.segments[segment].cell_type != cellType::FUNGI) {
          // Non-fungal particles are outside the P15 metric graph.  In
          // particular, do not require their owning-volume fields merely to
          // prove that an unrelated O07 operator leaves them byte-untouched.
          continue;
        }
        concentration[segment] = snapshot[segment] /
                                 graph.segments[segment].volume;
        if (!finite(concentration[segment])) {
          graphAbort("nonfinite D concentration in common O07 snapshot");
        }
        local_min[segment] = concentration[segment];
        local_max[segment] = concentration[segment];
      }
      std::vector<Real> request(pairs.size(), 0.0);
      for (std::size_t pair = 0; pair < pairs.size(); ++pair) {
        const auto& connection = pairs[pair];
        const Real amount = connection.conductance *
            (concentration[connection.first_segment] -
             concentration[connection.second_segment]) * dt;
        if (!finite(amount)) graphAbort("nonfinite virtual-pair request");
        request[pair] = amount;
        if (amount > 0.0) {
          outgoing[connection.first_segment] += amount;
        } else if (amount < 0.0) {
          outgoing[connection.second_segment] += -amount;
        }
        local_min[connection.first_segment] = std::min(
            local_min[connection.first_segment],
            concentration[connection.second_segment]);
        local_max[connection.first_segment] = std::max(
            local_max[connection.first_segment],
            concentration[connection.second_segment]);
        local_min[connection.second_segment] = std::min(
            local_min[connection.second_segment],
            concentration[connection.first_segment]);
        local_max[connection.second_segment] = std::max(
            local_max[connection.second_segment],
            concentration[connection.first_segment]);
      }

      std::vector<Real> scale(snapshot.size(), 1.0);
      for (std::size_t segment = 0; segment < snapshot.size(); ++segment) {
        if (outgoing[segment] > 0.0) {
          scale[segment] = std::min(
              Real(1.0), std::max(Real(0.0), snapshot[segment]) /
                             outgoing[segment]);
          if (!finite(scale[segment]) || scale[segment] < 0.0 ||
              scale[segment] > 1.0) {
            graphAbort("invalid bonded-D donor scale");
          }
          ledger.minimum_donor_scale = std::min(
              ledger.minimum_donor_scale, scale[segment]);
          if (1.0-scale[segment] > 64.0*binary64_epsilon) {
            ++ledger.material_cap_activations;
          }
        }
      }
      if (ledger.material_cap_activations > 0 &&
          !binding.cap_fault_injection) {
        amrex::Abort("BONDED_D_CAP_ACTIVATED");
      }

      std::vector<Real> delta(snapshot.size(), 0.0);
      for (std::size_t pair = 0; pair < pairs.size(); ++pair) {
        const auto& connection = pairs[pair];
        const Real absolute_request = std::abs(request[pair]);
        int donor = -1;
        if (request[pair] > 0.0) donor = connection.first_segment;
        if (request[pair] < 0.0) donor = connection.second_segment;
        const Real accepted = donor < 0 ? 0.0 :
                              absolute_request*scale[donor];
        const Real signed_accepted = request[pair] >= 0.0 ?
                                     accepted : -accepted;
        delta[connection.first_segment] -= signed_accepted;
        delta[connection.second_segment] += signed_accepted;
        ledger.requested += absolute_request;
        ledger.accepted += accepted;
        ledger.rejected += absolute_request-accepted;
        ledger.gross_absolute_accepted += accepted;
      }

      Real before_sum = 0.0;
      Real after_sum = 0.0;
      for (std::size_t segment = 0; segment < snapshot.size(); ++segment) {
        before_sum += snapshot[segment];
        if (graph.segments[segment].cell_type != cellType::FUNGI) {
          amounts[segment] = snapshot[segment];
          after_sum += snapshot[segment];
          continue;
        }
        Real updated = snapshot[segment] + delta[segment];
        const Real amount_scale = std::abs(snapshot[segment]) +
                                  std::abs(delta[segment]);
        if (!finite(updated) ||
            updated < -BMXPhosphorus::localTolerance(amount_scale)) {
          graphAbort("bonded-D update produced a negative amount");
        }
        if (updated < 0.0) updated = 0.0;
        const Real updated_concentration =
            updated/graph.segments[segment].volume;
        const Real extremum_scale = std::abs(updated_concentration) +
                                    std::abs(local_min[segment]) +
                                    std::abs(local_max[segment]);
        const Real extremum_tolerance =
            BMXPhosphorus::localTolerance(extremum_scale);
        if (!finite(updated_concentration) ||
            (!binding.cap_fault_injection &&
             (updated_concentration <
                  local_min[segment]-extremum_tolerance ||
              updated_concentration >
                  local_max[segment]+extremum_tolerance))) {
          graphAbort("bonded-D update created a new concentration extremum");
        }
        amounts[segment] = updated;
        after_sum += updated;
      }
      const Real conservation_scale = std::abs(before_sum) +
                                      std::abs(after_sum);
      if (!finite(before_sum) || !finite(after_sum) ||
          std::abs(after_sum-before_sum) >
              BMXPhosphorus::integratedTolerance(conservation_scale)) {
        graphAbort("bonded-D substep violates global pair conservation");
      }
    }

    commitDAmounts(particles, graph, amounts);
    const auto after = BMXPhosphorus::computeInternalAmounts(particles);
    BMXPhosphorus::requireIntegratedConservation(
        before, after, "P15 O07 canonical bonded-D transport");
    recordBondedStep(ledger);
  }
}
