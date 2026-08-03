#
#     Copyright (c) 2013 Battelle Memorial Institute
#     Licensed under modified BSD License. A copy of this license can be found
#     in the LICENSE file in the top level directory of this distribution.
#
target_include_directories( bmxcore
   PUBLIC
   $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}>)

target_sources( bmxcore
   PRIVATE
   bmx_phosphorus_uptake.cpp
   bmx_phosphorus_uptake_K.H
   bmx_phosphorus_reactions.cpp
   bmx_phosphorus_reactions_K.H
   bmx_phosphorus_export.cpp
   bmx_phosphorus_export_K.H
   bmx_p15_stage0.cpp
   bmx_p15_stage0_K.H
   bmx_chem.H
   bmx_chem_K.H
   bmx_cell_interaction.H
   bmx_cell_interaction_K.H
   bmx_chem.cpp
   bmx_cell_interaction.cpp
   )
