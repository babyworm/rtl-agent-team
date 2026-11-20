# Native phase team

Use the team name, phase and coordinator agent supplied by the invoking skill.
The main session owns the team lifecycle. On hosts without Claude Code native
teams, use the phase's sequential workflow and the host's workers for independent
assignments. Return the same gate results. On Claude Code:

1. Call `TeamCreate` for this team. If it fails, use the skill's sequential entry
   with the original arguments.
2. Create `.rat/state/` and `.rat/scratch/phase-<number>/` as needed. From the
   main session, use `Write` on `.rat/state/team-config.json` with
   `team_mode: true`, the actual `team_name` and `phase`, and
   `coordinator_name: "coordinator"`. Include the invoking skill's resolved session
   ID as `leader_session_id` for the spawn manifest. The Write hook records ownership.
3. Spawn the coordinator with the team workflow and the full phase request:

   ```text
   Agent(team_name=team_name, subagent_type=coordinator_agent, name="coordinator",
         description="Coordinate the requested phase",
         prompt="MODE=team. $ARGUMENTS. Send the leader any ready assignments that need a worker, and the phase gate result at handoff.")
   ```

4. For independent work identified by the coordinator, assign an available teammate
   or use `Agent` to start the specialist best suited to the assignment.
   Use the host's worker selection from `{plugin_root}/runtime/model-selection.md`.
   Supply the assignment, inputs, output path and coordinator recipient.
   The coordinator integrates worker evidence and applies the same phase and
   cross-review policy as in sequential mode.
5. Wait for the coordinator's completion message after the phase gate and required
   deliverables. If it reports a blocker, carry the failure or open decision back
   to the caller. An empty task list cannot establish a phase verdict.
6. At completion, cancellation or a blocker that ends the run, send each teammate
   a `shutdown_request`, wait
   for shutdown, then call `TeamDelete()`. Remove this team's
   `.rat/state/team-config.json` after teardown. Clean up its temporary scratch
   files once the coordinator has saved the evidence needed for handoff or resume.
