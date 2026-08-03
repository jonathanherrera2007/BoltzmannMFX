#include <AMReX.H>
#include <AMReX_PlotFileUtil.H>

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char* argv[])
{
  amrex::Initialize(argc, argv, false);
  int result = 0;
  try {
    if (amrex::command_argument_count() != 3) {
      throw std::runtime_error("usage: c10_plot_extract PLOT VARIABLE OUTPUT");
    }
    const std::string plot_path = amrex::get_command_argument(1);
    const std::string variable = amrex::get_command_argument(2);
    const std::string output_path = amrex::get_command_argument(3);
    amrex::PlotFileData plot(plot_path);
    if (plot.finestLevel() != 0 || plot.spaceDim() != 3) {
      throw std::runtime_error("C10 extractor requires one uniform 3-D level");
    }
    bool found = false;
    for (const auto& name : plot.varNames()) found = found || name == variable;
    if (!found) throw std::runtime_error("plot variable not found: " + variable);
    const auto domain = plot.probDomain(0);
    const auto lo = amrex::lbound(domain);
    const auto hi = amrex::ubound(domain);
    const int nx = hi.x - lo.x + 1;
    const int ny = hi.y - lo.y + 1;
    const int nz = hi.z - lo.z + 1;
    std::vector<amrex::Real> values(
        static_cast<std::size_t>(nx) * ny * nz);
    auto field = plot.get(0, variable);
    for (amrex::MFIter mfi(field); mfi.isValid(); ++mfi) {
      const auto box = mfi.validbox() & domain;
      const auto array = field.const_array(mfi);
      const auto blo = amrex::lbound(box);
      const auto bhi = amrex::ubound(box);
      for (int k = blo.z; k <= bhi.z; ++k) {
        for (int j = blo.y; j <= bhi.y; ++j) {
          for (int i = blo.x; i <= bhi.x; ++i) {
            const std::size_t index =
                static_cast<std::size_t>(i - lo.x) +
                static_cast<std::size_t>(nx) * (j - lo.y) +
                static_cast<std::size_t>(nx) * ny * (k - lo.z);
            values[index] = array(i,j,k);
          }
        }
      }
    }
    std::ofstream output(output_path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot open output");
    output << "C10_PLOT_FIELD_V1 " << nx << ' ' << ny << ' ' << nz
           << ' ' << std::setprecision(17) << plot.time() << '\n';
    output << std::setprecision(17);
    for (const auto value : values) output << value << '\n';
  } catch (const std::exception& error) {
    std::cerr << "C10_PLOT_EXTRACT FAIL " << error.what() << '\n';
    result = 1;
  }
  amrex::Finalize();
  return result;
}
