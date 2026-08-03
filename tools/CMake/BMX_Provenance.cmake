# BMX RG-SW -- build provenance resolution.  Repairs D-C04-08.
#
# WHY THIS EXISTS
# ---------------
# A release build must record which commit produced it. Three compounding
# defects meant it did not:
#
#   1. get_git_info() in BMX_Utils.cmake was invoked as `get_git_info( )`, with
#      no arguments, so its `${ARGC} GREATER 0` guards never fired and it
#      captured nothing into any variable on ANY platform. It only printed.
#   2. The provenance that actually reached the binary came from AMReX's
#      generate_buildinfo(), which runs `git describe` in the source directory.
#      In a linked worktree the `.git` entry is a FILE holding an absolute
#      `gitdir:` path. That path is recorded in the syntax of the machine that
#      created the worktree, so a Windows-created worktree is unresolvable from
#      Linux and `git describe` yields an empty string.
#   3. writeBuildInfo() then skipped the line entirely when the hash was empty
#      (`if (strlen(githash1) > 0)`), so a build with no provenance looked
#      exactly like a build that simply did not print it. Failing open.
#
# WHAT THIS DOES
# --------------
# Resolves provenance independently of AMReX, handling:
#   * `.git` as a DIRECTORY  (ordinary checkout)
#   * `.git` as a FILE       (linked worktree, or submodule)
#   * a `gitdir:` that is relative (resolved against the source directory)
#   * a `gitdir:` that is absolute but written in another platform's syntax
#     (translated; see bmx_translate_foreign_path)
# and never assumes `.git` is a directory.
#
# It emits commit, short commit, branch, dirty flag and a describe string, and
# a status of RESOLVED / UNAVAILABLE. When BMX_REQUIRE_PROVENANCE is ON the
# configure step FAILS rather than producing an unattributable artefact.
#
# Can also be driven standalone, which is what the regression fixture uses:
#   cmake -DBMX_PROVENANCE_PROBE=<source-dir> -P tools/CMake/BMX_Provenance.cmake

cmake_minimum_required(VERSION 3.14)

# Translate an absolute path written in another platform's syntax.
# Returns the input unchanged when no translation applies.
function(bmx_translate_foreign_path _in _out)
  set(_p "${_in}")
  set(_candidates "")

  # Windows drive-letter form -> POSIX mount points used by WSL and Git-Bash.
  if(_p MATCHES "^([A-Za-z]):[/\\\\](.*)$")
    string(TOLOWER "${CMAKE_MATCH_1}" _drive)
    string(REPLACE "\\" "/" _rest "${CMAKE_MATCH_2}")
    list(APPEND _candidates "/mnt/${_drive}/${_rest}" "/${_drive}/${_rest}"
                            "/cygdrive/${_drive}/${_rest}")
  endif()

  # POSIX mount point -> Windows drive-letter form.
  if(_p MATCHES "^/(mnt|cygdrive)/([A-Za-z])/(.*)$")
    string(TOUPPER "${CMAKE_MATCH_2}" _drive)
    list(APPEND _candidates "${_drive}:/${CMAKE_MATCH_3}")
  endif()
  if(_p MATCHES "^/([A-Za-z])/(.*)$")
    string(TOUPPER "${CMAKE_MATCH_1}" _drive)
    list(APPEND _candidates "${_drive}:/${CMAKE_MATCH_2}")
  endif()

  foreach(_c IN LISTS _candidates)
    if(EXISTS "${_c}")
      set(${_out} "${_c}" PARENT_SCOPE)
      return()
    endif()
  endforeach()

  set(${_out} "${_in}" PARENT_SCOPE)
endfunction()

# Locate the real git directory for a source tree.
# Sets <_out_gitdir> to a usable path, or "" when it cannot be established.
function(bmx_resolve_git_dir _src _out_gitdir _out_note)
  set(_note "")
  set(_dotgit "${_src}/.git")

  if(NOT EXISTS "${_dotgit}")
    set(${_out_gitdir} "" PARENT_SCOPE)
    set(${_out_note} "no .git entry at ${_src}" PARENT_SCOPE)
    return()
  endif()

  # Ordinary checkout: .git is a directory. Never assume this case.
  if(IS_DIRECTORY "${_dotgit}")
    set(${_out_gitdir} "${_dotgit}" PARENT_SCOPE)
    set(${_out_note} "ordinary checkout" PARENT_SCOPE)
    return()
  endif()

  # Linked worktree or submodule: .git is a file holding "gitdir: <path>".
  file(READ "${_dotgit}" _content)
  string(STRIP "${_content}" _content)
  if(NOT _content MATCHES "^gitdir:[ \t]*(.+)$")
    set(${_out_gitdir} "" PARENT_SCOPE)
    set(${_out_note} ".git is a file but has no 'gitdir:' line" PARENT_SCOPE)
    return()
  endif()
  string(STRIP "${CMAKE_MATCH_1}" _gitdir)
  string(REPLACE "\\" "/" _gitdir "${_gitdir}")

  # Is this pointer absolute?
  #
  # CMake's IS_ABSOLUTE is evaluated with HOST syntax: on Linux it reports
  # FALSE for "C:/Users/...", so a Windows-written pointer would be silently
  # joined onto the source directory and produce the nonsense path
  # "<src>/C:/Users/...". That is precisely how D-C04-08 presented. Recognise
  # the drive-letter form explicitly instead of trusting IS_ABSOLUTE alone.
  set(_is_abs FALSE)
  if(IS_ABSOLUTE "${_gitdir}" OR _gitdir MATCHES "^[A-Za-z]:[/\\\\]")
    set(_is_abs TRUE)
  endif()

  if(_is_abs)
    set(_note "linked worktree, absolute gitdir")
  else()
    get_filename_component(_gitdir "${_src}/${_gitdir}" ABSOLUTE)
    set(_note "linked worktree, relative gitdir")
  endif()

  # This is the D-C04-08 failure: an absolute pointer written on another
  # platform. Translate rather than give up.
  if(NOT EXISTS "${_gitdir}")
    bmx_translate_foreign_path("${_gitdir}" _translated)
    if(EXISTS "${_translated}")
      set(_note "${_note}, translated across platforms")
      set(_gitdir "${_translated}")
    endif()
  endif()

  if(NOT EXISTS "${_gitdir}")
    set(${_out_gitdir} "" PARENT_SCOPE)
    set(${_out_note} "gitdir '${_gitdir}' does not exist on this host" PARENT_SCOPE)
    return()
  endif()

  set(${_out_gitdir} "${_gitdir}" PARENT_SCOPE)
  set(${_out_note} "${_note}" PARENT_SCOPE)
endfunction()

# Run a git command against an explicitly resolved git dir + work tree.
# Uses RESULT_VARIABLE: git writes to stderr for benign reasons, so testing
# the error stream (as the previous macro did) misclassifies success.
function(_bmx_git _gitdir _src _out_var)
  execute_process(
    COMMAND ${GIT_EXECUTABLE} --git-dir=${_gitdir} --work-tree=${_src} ${ARGN}
    OUTPUT_VARIABLE _o ERROR_VARIABLE _e RESULT_VARIABLE _rc
    OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_STRIP_TRAILING_WHITESPACE)
  if(NOT _rc EQUAL 0)
    set(${_out_var} "" PARENT_SCOPE)
  else()
    set(${_out_var} "${_o}" PARENT_SCOPE)
  endif()
endfunction()

# Main entry point. Defines in the caller's scope:
#   BMX_GIT_COMMIT BMX_GIT_COMMIT_SHORT BMX_GIT_BRANCH BMX_GIT_DIRTY
#   BMX_GIT_DESCRIBE BMX_PROVENANCE_STATUS BMX_PROVENANCE_NOTE
function(bmx_resolve_provenance _src)
  set(BMX_GIT_COMMIT "" PARENT_SCOPE)
  set(BMX_GIT_COMMIT_SHORT "" PARENT_SCOPE)
  set(BMX_GIT_BRANCH "" PARENT_SCOPE)
  set(BMX_GIT_DIRTY "unknown" PARENT_SCOPE)
  set(BMX_GIT_DESCRIBE "" PARENT_SCOPE)
  set(BMX_PROVENANCE_STATUS "UNAVAILABLE" PARENT_SCOPE)

  if(NOT GIT_EXECUTABLE)
    find_package(Git QUIET)
  endif()
  if(NOT GIT_EXECUTABLE)
    set(BMX_PROVENANCE_NOTE "git executable not found" PARENT_SCOPE)
    return()
  endif()

  bmx_resolve_git_dir("${_src}" _gitdir _note)
  if(NOT _gitdir)
    set(BMX_PROVENANCE_NOTE "${_note}" PARENT_SCOPE)
    return()
  endif()

  _bmx_git("${_gitdir}" "${_src}" _commit rev-parse HEAD)
  if(NOT _commit)
    set(BMX_PROVENANCE_NOTE "resolved gitdir '${_gitdir}' but rev-parse HEAD failed" PARENT_SCOPE)
    return()
  endif()

  _bmx_git("${_gitdir}" "${_src}" _short rev-parse --short=12 HEAD)
  _bmx_git("${_gitdir}" "${_src}" _branch rev-parse --abbrev-ref HEAD)
  _bmx_git("${_gitdir}" "${_src}" _desc describe --abbrev=12 --dirty --always --tags)
  # Porcelain is empty exactly when the work tree is clean.
  _bmx_git("${_gitdir}" "${_src}" _status status --porcelain)
  if(_status STREQUAL "")
    set(_dirty "clean")
  else()
    set(_dirty "dirty")
  endif()

  set(BMX_GIT_COMMIT       "${_commit}" PARENT_SCOPE)
  set(BMX_GIT_COMMIT_SHORT "${_short}"  PARENT_SCOPE)
  set(BMX_GIT_BRANCH       "${_branch}" PARENT_SCOPE)
  set(BMX_GIT_DIRTY        "${_dirty}"  PARENT_SCOPE)
  set(BMX_GIT_DESCRIBE     "${_desc}"   PARENT_SCOPE)
  set(BMX_PROVENANCE_STATUS "RESOLVED"  PARENT_SCOPE)
  set(BMX_PROVENANCE_NOTE   "${_note}"  PARENT_SCOPE)
endfunction()

# Fail closed. Call after bmx_resolve_provenance when the build is intended to
# carry release evidence. An unattributable artefact is worse than no artefact.
function(bmx_require_provenance)
  if(NOT BMX_PROVENANCE_STATUS STREQUAL "RESOLVED")
    message(FATAL_ERROR
      "BMX_REQUIRE_PROVENANCE is ON but build provenance could not be established.\n"
      "  reason: ${BMX_PROVENANCE_NOTE}\n"
      "A build that cannot say which commit produced it must not carry release "
      "evidence. Either configure from a checkout whose .git resolves on this "
      "host, run tools/repro/repair_worktree_provenance.sh, or configure with "
      "-DBMX_REQUIRE_PROVENANCE=OFF for a non-release build.")
  endif()
endfunction()

# ---------------------------------------------------------------------------
# Standalone probe mode, used by the regression fixture so it exercises exactly
# the code the build uses rather than a reimplementation of it.
#   cmake -DBMX_PROVENANCE_PROBE=<src> -P BMX_Provenance.cmake
# ---------------------------------------------------------------------------
if(DEFINED BMX_PROVENANCE_PROBE)
  find_package(Git QUIET)
  bmx_resolve_provenance("${BMX_PROVENANCE_PROBE}")
  message(STATUS "BMX_PROVENANCE_STATUS=${BMX_PROVENANCE_STATUS}")
  message(STATUS "BMX_PROVENANCE_NOTE=${BMX_PROVENANCE_NOTE}")
  message(STATUS "BMX_GIT_COMMIT=${BMX_GIT_COMMIT}")
  message(STATUS "BMX_GIT_COMMIT_SHORT=${BMX_GIT_COMMIT_SHORT}")
  message(STATUS "BMX_GIT_BRANCH=${BMX_GIT_BRANCH}")
  message(STATUS "BMX_GIT_DIRTY=${BMX_GIT_DIRTY}")
  message(STATUS "BMX_GIT_DESCRIBE=${BMX_GIT_DESCRIBE}")
endif()
