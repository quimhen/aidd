// AIDD OpenCode plugin: a real gate, not a nudge.
//
// Contract
//   tool.execute.before  When the project has .aidd/AIDD.md, the event
//     {sessionID, cwd, tool, args} is sent on stdin to
//     `python .aidd/hooks/host_adapter.py opencode pre`. Exit code 2 BLOCKS the
//     tool call: this plugin throws Error(stderr), and OpenCode aborts the call
//     and shows the message to the model. Blocking is real, not advisory.
//   tool.execute.after   Same adapter with phase `post` (evidence marking).
//     Never throws.
//   Fail open: a spawn error, a missing python or any exit code other than 2
//     lets the call proceed, so a host problem never wedges the session.
//     Fail CLOSED: an explicit exit 2 from the adapter blocks, and so does an
//     adapter timeout (ETIMEDOUT), so a padded command cannot skip the gate.
//   Only mutating tools are gated (write/edit/patch/bash...): other tools return
//     before any spawn, so reads/greps pay no Python cost. A missing python
//     (ENOENT) still fails open but warns once per session on stderr.
//   Not an AIDD project (no .aidd/AIDD.md under the plugin directory): no-op.
//
// Reminder dropped: the old once-per-session shell reminder prepended an echo
// to the user's command by mutating output.args.command. The API offers no
// other safe channel, and the gate now blocks with an actionable message, so
// the reminder was removed instead of mutating user commands.
//
// Sources (OpenCode plugin API, checked 2026-10-13)
//   https://opencode.ai/docs/plugins/  (handler is (input, output); input.tool
//     is the tool name; output.args holds the arguments; throwing an Error in
//     tool.execute.before blocks the call)
//   https://unpkg.com/@opencode-ai/plugin/dist/index.d.ts  (types)
//     before: (input {tool, sessionID, callID}, output {args})
//     after:  (input {tool, sessionID, callID, args}, output {title, output, metadata})
//     PluginInput includes directory and worktree.
// Note the asymmetry: args arrive in output.args on `before` and in input.args
// on `after`.
import { existsSync } from "fs";
import { join } from "path";
import { spawnSync } from "child_process";

const adapterTimeoutMs = 20000;

// Cheap JS pre-filter: only mutating tools reach Python (saves two spawns per
// read/grep/glob call). Keep conceptually identical to the tool filter in
// .aidd/hooks/host_adapter.py (skill/hooks/host_adapter.py).
const gatedTools = new Set(["write", "edit", "multiedit", "patch", "apply_patch", "bash"]);
const gatedPattern = /(write|edit|patch|replace|create|append|insert|save|delete|remove|move|rename)/;
const readOnlyPrefix = /^(read|glob|grep|list|search|fetch|web|find)/;
const isGatedTool = (tool) => {
  const name = String(tool || "").toLowerCase();
  if (gatedTools.has(name)) return true;
  return gatedPattern.test(name) && !readOnlyPrefix.test(name);
};

let warnedNoPython = false;

const runAdapter = (directory, phase, event) => {
  try {
    const script = join(directory, ".aidd", "hooks", "host_adapter.py");
    const result = spawnSync("python", [script, "opencode", phase], {
      input: JSON.stringify(event),
      encoding: "utf8",
      timeout: adapterTimeoutMs,
      windowsHide: true,
      cwd: directory,
    });
    if (result.error && result.error.code === "ENOENT" && !warnedNoPython) {
      warnedNoPython = true;
      console.error("[aidd] python not found on PATH: the AIDD gate is inactive (run `aidd doctor`)");
    }
    if (result.error && result.error.code === "ETIMEDOUT") {
      // fail CLOSED on a gate that cannot answer in time (a padded command must not skip the block)
      return { status: 2, stderr: "aidd: the gate did not answer in time; the call is blocked (run `aidd doctor`)" };
    }
    if (result.error || result.signal) return null;
    return result;
  } catch (error) {
    return null;
  }
};

export const AiddPlugin = async ({ directory }) => {
  const isAiddProject = () => existsSync(join(directory, ".aidd", "AIDD.md"));

  return {
    "tool.execute.before": async (input, output) => {
      if (!isGatedTool(input && input.tool)) return;
      if (!isAiddProject()) return;
      const result = runAdapter(directory, "pre", {
        sessionID: input.sessionID,
        cwd: directory,
        tool: input.tool,
        args: (output && output.args) || {},
      });
      if (result && result.status === 2) {
        throw new Error((result.stderr || "").trim() || "blocked by AIDD");
      }
    },

    "tool.execute.after": async (input) => {
      try {
        if (!isGatedTool(input && input.tool)) return;
        if (!isAiddProject()) return;
        runAdapter(directory, "post", {
          sessionID: input.sessionID,
          cwd: directory,
          tool: input.tool,
          args: input.args || {},
        });
      } catch (error) {
        // post never throws
      }
    },
  };
};

// opencode 2.x loads a default {id, setup} and has no tool.execute hooks, so the gate is inactive there (setup is a no-op); opencode 1.x uses server.
export default { id: "aidd", server: AiddPlugin, setup() {} };
