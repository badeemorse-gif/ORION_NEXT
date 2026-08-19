# Canonical Phase Contract

## Scope
Define the minimum governance contract for an ORION phase, including ownership boundaries, verification gates, and auditable completion evidence.

## Contracts
- Phase work starts from an explicit baseline/parent SHA.
- Production contracts remain unchanged unless explicitly authorized by the phase scope.
- Verification must identify the exact source SHA under test.
- CI evidence must be attributable to the exact checked-out revision.
- A phase is not complete without the required tests, parity evidence, and clean working tree.

## Forbidden Changes
- Unapproved Production changes.
- Changes outside the declared phase ownership boundary.
- Main-branch modification as part of phase implementation.
- Unapproved merge, rebase, cherry-pick, reset, or force-push.
- Suppression or weakening of a failing contract solely to obtain a green verification result.

## Definition of Done
- Declared scope is implemented completely.
- Required tests pass.
- Exact-source checkout is verified in CI.
- Working tree is clean after verification.
- Required evidence artifact is uploaded.
- Changed paths remain within the declared scope.

## Required Evidence
- HEAD SHA
- Parent/baseline SHA
- Changed paths
- Expected SHA
- Actual checked-out SHA
- Test command and result
- Working-tree result
- CI run ID
- Evidence artifact
- Final phase status
