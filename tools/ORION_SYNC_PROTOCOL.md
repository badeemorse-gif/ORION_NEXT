# ORION Synchronization Protocol

## Source of truth

`origin/<branch>` on GitHub is the source of truth for project synchronization.
Local working-tree changes are never promoted by the synchronization tool.

## Safe synchronization flow

1. Resolve the project root from the location of the tool itself. No fixed user path is assumed.
2. Validate that the checkout is the ORION_NEXT Git repository.
3. Fetch the requested branch from `origin`.
4. Read the exact target commit and target synchronization-tool blob from GitHub.
5. If local changes or removable paths exist, create a safety copy outside the repository before destructive synchronization.
6. If the local synchronization tool is older than the GitHub target, materialize and execute the GitHub version before synchronization continues.
7. Reset the working tree to the exact GitHub target branch.
8. Synchronize submodules and clean their working trees.
9. Verify commit identity, tracked-tree parity, staged state, and ignored/untracked state.
10. Report the exact branch, commit, root, tool version, and backup location.

## Important guarantees

- No `git commit` is performed.
- No `git push` is performed.
- `.git` is preserved.
- A failed safety backup stops synchronization before destructive reset.
- The synchronization tool can self-refresh from the selected GitHub branch, preventing a stale local copy of the tool from controlling the synchronization process.
- `tools/orion_sync_verify.py` independently checks byte-for-byte project parity against a selected GitHub branch without resetting or cleaning the project.

## Normal workflow for development

**Repository modification → GitHub commit → GitHub → Local sync → test → decision.**

If a test fails, the next code modification is made in GitHub first, then synchronized locally and tested again.
