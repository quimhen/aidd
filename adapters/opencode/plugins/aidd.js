// AIDD OpenCode plugin — nudges the model toward the AIDD pipeline before a
// shell command runs, once per session, the same way graphify.js does for its
// own reminder. This mirrors Claude Code's prompt_trigger.py hook, adapted to
// the one plugin hook point this project has confirmed working in OpenCode
// (tool.execute.before). OpenCode's plugin API does not expose a distinct
// "user prompt submitted" event or a per-tool-name gate the way Claude Code's
// hook system does, so this cannot hard-block a Write/Edit call the way
// require_aidd.py does in Claude Code — it can only remind before the next
// shell command. Treat AGENTS.md as the primary, always-read instruction
// layer; this plugin is a best-effort nudge on top of it, not an enforcement
// gate.
import { existsSync } from "fs";
import { join } from "path";

export const AiddPlugin = async ({ directory }) => {
  let reminded = false;

  return {
    "tool.execute.before": async (input, output) => {
      if (reminded) return;
      if (!existsSync(join(directory, ".aidd", "AIDD.md"))) return;
      if (input.tool !== "bash") return;

      output.args.command =
        'echo "[aidd] This project runs every requirement/change/fix through AIDD (see AGENTS.md). Before implementing, run: python .aidd/scripts/find_spec.py <keywords or a SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn code> to check whether this amends an existing spec under specs/ instead of creating a new one." && ' +
        output.args.command;
      reminded = true;
    },
  };
};
