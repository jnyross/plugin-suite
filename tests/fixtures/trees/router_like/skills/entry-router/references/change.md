# Change Playbook

## Trigger

Implement or build requests that authorize edits.

## Intent

Apply the smallest change that satisfies the request.

## Workflow

1. Reproduce or observe the behavior being changed.
2. Edit only the files the request names or implies.
3. Run the narrowest check that proves the outcome.

## Output

The diff, the check result, and a one-line summary of effect.

## Boundaries

Never reformat unrelated code while implementing a change.
