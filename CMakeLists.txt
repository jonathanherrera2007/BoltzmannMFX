#
#     Copyright (c) 2013 Battelle Memorial Institute
#     Licensed under modified BSD License. A copy of this license can be found
#     in the LICENSE file in the top level directory of this distribution.
#

cmake_minimum_required(VERSION 3.14)

project(BMX-Exa
   # VERSION <version>
   DESCRIPTION  "A multiphase modeling tool for the exascale"
   HOMEPAGE_URL "https://amrex-codes.github.io/BMX-Exa/"
   LANGUAGES    C CXX
   )

# Set the search path for cmake modules
set( CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR}/tools/CMake )

#
# This sets CMAKE_CXX_FLAGS_<CONFIG> to a default value
# if the variable is empty
#
if( NOT CMAKE_CXX_FLAGS_DEBUG )
   set(CMAKE_CXX_FLAGS_DEBUG "-g")
endif()

if (BMX_DEBUG EQUAL TRUE)
  add_compile_definitions(DEBUG)
endif()


if( NOT CMAKE_CXX_FLAGS_RELEASE )
   if (BMX_DEBUG EQUAL TRUE)
     set(CMAKE_CXX_FLAGS_RELEASE "-O2")
   else()
     set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG")
   endif()
endif()

# Load utilities and BMX options module
include( BMX_Utils )

# Creates `compile_commands.json` in the build build directory
#  `compile_commands.json` contains compiler flags used by plugins like YouCompleteMe
set( CMAKE_EXPORT_COMPILE_COMMANDS ON )

# Set default build type to Release
if ( NOT CMAKE_BUILD_TYPE )
   message(STATUS "Setting build type to Release as none was specified.")
   set( CMAKE_BUILD_TYPE Release )
else ()
   message(STATUS "Build type set by user to '${CMAKE_BUILD_TYPE}'.")
endif()

find_program(CCACHE_FOUND ccache)
if(CCACHE_FOUND)
  set( CMAKE_CXX_COMPILER_LAUNCHER ccache )
  set( CMAKE_CUDA_COMPILER_LAUNCHER ccache )
endif()

# Turn on new chemistry module
add_compile_definitions(NEW_CHEM)
add_compile_definitions(DEP_DEBUG)

# We want to offer the user some core options, i.e. MPI, OpenMP, CUDA, HYPRE
# and floating-point exceptions, which require related AMReX components to
# be enabled in the installation.
# In STANDALONE mode, find_package will make sure these options are available
# IN SUPERBUILD mode, These options will supersede AMReX options with the same name
option( BMX_OMP    "Enable OpenMP" NO )
option( BMX_MPI    "Enable MPI"   YES )

include(CMakeDependentOption)
cmake_dependent_option( BMX_MPI_THREAD_MULTIPLE
   "whether to initialize MPI so that multiple threads can make MPI calls at the same time"  OFF
   "BMX_MPI" OFF)

option( BMX_HYPRE  "Enable HYPRE"  NO )
option( BMX_FPE    "Enable Floating Point Exceptions checks" NO )

#
# GPU backends    =============================================================
#
set(BMX_GPU_BACKEND_VALUES NONE SYCL CUDA HIP)
set(BMX_GPU_BACKEND NONE CACHE STRING "On-node, accelerated GPU backend: <NONE,SYCL,CUDA,HIP>")
set_property(CACHE BMX_GPU_BACKEND PROPERTY STRINGS ${BMX_GPU_BACKEND_VALUES})
if (NOT BMX_GPU_BACKEND IN_LIST BMX_GPU_BACKEND_VALUES)
   message(FATAL_ERROR "BMX_GPU_BACKEND=${BMX_GPU_BACKEND} is not allowed."
      " Must be one of ${BMX_GPU_BACKEND_VALUES}")
endif ()

if (NOT BMX_GPU_BACKEND STREQUAL NONE)
   message( STATUS "   BMX_GPU_BACKEND = ${BMX_GPU_BACKEND}")
endif ()

if (BMX_GPU_BACKEND STREQUAL SYCL)
   set(BMX_DPCPP ON  )
   set(BMX_CUDA  OFF )
   set(BMX_HIP   OFF )
elseif (BMX_GPU_BACKEND STREQUAL CUDA)
   set(BMX_DPCPP OFF )
   set(BMX_CUDA  ON  )
   set(BMX_HIP   OFF )
elseif (BMX_GPU_BACKEND STREQUAL HIP)
   set(BMX_DPCPP OFF )
   set(BMX_CUDA  OFF )
   set(BMX_HIP   ON  )
elseif ()
   set(BMX_DPCPP OFF )
   set(BMX_CUDA  OFF )
endif()

# CSG support
option( BMX_CSG "Build with CSG support" OFF)

if (BMX_CUDA)
  # CMake 3.18+: CMAKE_CUDA_ARCHITECTURES
  # https://cmake.org/cmake/help/latest/policy/CMP0104.html
  if(POLICY CMP0104)
    cmake_policy(SET CMP0104 OLD)
  endif()
  enable_language(CUDA)
endif ()

# Setup AMReX
include(BMXSetupAMReX)

get_git_info( )

#
# Build provenance (D-C04-08).
#
# get_git_info() above is invoked with no arguments, so its ${ARGC} guards
# never fire and it captures nothing -- it only prints. Provenance that the
# binary can actually report is resolved here instead, and works in linked
# worktrees on both Windows and Linux.
#
# BMX_REQUIRE_PROVENANCE is OFF by default so ordinary development builds are
# unaffected. Turn it ON for any build whose output is intended as release
# evidence; configure then fails rather than emitting an unattributable binary.
#
include(BMX_Provenance)
option(BMX_REQUIRE_PROVENANCE
       "Fail configuration if build provenance cannot be established" OFF)

bmx_resolve_provenance("${CMAKE_CURRENT_SOURCE_DIR}")
set(BMX_PROVENANCE_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

if(BMX_PROVENANCE_STATUS STREQUAL "RESOLVED")
  message(STATUS "BMX provenance: ${BMX_GIT_COMMIT} (${BMX_GIT_BRANCH}, ${BMX_GIT_DIRTY}) -- ${BMX_PROVENANCE_NOTE}")
else()
  message(WARNING "BMX provenance UNAVAILABLE: ${BMX_PROVENANCE_NOTE}")
endif()

if(BMX_REQUIRE_PROVENANCE)
  bmx_require_provenance()
endif()

configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/CMake/bmx_provenance.H.in
  ${CMAKE_CURRENT_BINARY_DIR}/bmx_generated/bmx_provenance.H
  @ONLY)

# Set some cache variable for the whole project
set( MAIN ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp CACHE INTERNAL "Main source file")

#
# Core BMX library
#
add_subdirectory(src)

# Print out config summary
print_bmx_configuration_summary(bmxcore)

add_executable(bmx ${MAIN})
target_link_libraries( bmx bmxcore )

# We should check what this line does
file( GLOB USR_OVERRIDES ${CMAKE_CURRENT_BINARY_DIR}/*.cpp)

if (BMX_CUDA)
   setup_target_for_cuda_compilation(bmx)
endif ()

# Tools
add_subdirectory(tools)

# Tags
include(BMX_Tags)
add_tags_targets()

# Copy compile_commands.json from the build directory to the project root directory
if ( EXISTS "${CMAKE_CURRENT_BINARY_DIR}/compile_commands.json" )
    execute_process( COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${CMAKE_CURRENT_BINARY_DIR}/compile_commands.json
        ${CMAKE_CURRENT_SOURCE_DIR}/compile_commands.json
  )
endif ()

if(BMX_CSG)
  target_link_libraries(bmxcore PRIVATE csg)
endif()

# Test cases
add_subdirectory(exec)
