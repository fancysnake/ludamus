#!/usr/bin/env bun

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { pathToFileURL } from "node:url";
import type {
  AgentDeviceClient,
  AgentDeviceSelectionOptions,
  CaptureSnapshotResult,
  SnapshotNode,
} from "agent-device";

type AgentDeviceModule = typeof import("agent-device");

type IosDeviceOptions = AgentDeviceSelectionOptions & {
  platform: "ios";
};

const env = process.env;
const baseUrl = env.BASE_URL ?? "http://localhost:8000";
const session = env.SESSION ?? "zagrajmy-ios-modal-local";
const targetTitle = env.TARGET_SESSION_TITLE ?? "Przygoda w Mieście Neonów";
const eventPath = env.EVENT_PATH ?? "/chronology/event/autumn-open/";
const targetQueryParam = env.TARGET_QUERY_PARAM ?? "session=3";
const deviceName = env.IOS_DEVICE_NAME ?? "iPhone 16";
const runtime = env.IOS_RUNTIME;
const providedUdid = env.UDID;

const importAgentDevice = async (): Promise<AgentDeviceModule> => {
  try {
    return await import("agent-device");
  } catch (error) {
    const candidates: string[] = [];
    try {
      const npmRoot = execFileSync("npm", ["root", "-g"], {
        encoding: "utf8",
      }).trim();
      candidates.push(`${npmRoot}/agent-device/dist/src/index.js`);
    } catch {
      // Ignore and try Bun's global install path below.
    }
    if (env.HOME) {
      candidates.push(
        `${env.HOME}/.bun/install/global/node_modules/agent-device/dist/src/index.js`,
      );
    }

    for (const candidate of candidates) {
      if (existsSync(candidate)) {
        return (await import(pathToFileURL(candidate).href)) as AgentDeviceModule;
      }
    }
    throw error;
  }
};

const { createAgentDeviceClient } = await importAgentDevice();
const client: AgentDeviceClient = createAgentDeviceClient({ session });

const deviceOptions: IosDeviceOptions = providedUdid
  ? { platform: "ios", udid: providedUdid }
  : { platform: "ios", device: deviceName };

const ensureSimulator = async (): Promise<string> => {
  if (providedUdid) return providedUdid;

  const result = await client.simulators.ensure({
    device: deviceName,
    ...(runtime ? { runtime } : {}),
    boot: true,
    reuseExisting: true,
  });
  return result.udid;
};

const takeSnapshot = async (): Promise<CaptureSnapshotResult> =>
  client.capture.snapshot({
    ...deviceOptions,
    interactiveOnly: true,
  });

const snapshotLabels = async (): Promise<string[]> => {
  const snapshot = await takeSnapshot();
  return snapshot.nodes
    .map((node) => node.label ?? node.value ?? "")
    .filter(Boolean);
};

const hasVisibleText = async (text: string): Promise<boolean> => {
  const labels = await snapshotLabels();
  return labels.some((label) => label.includes(text));
};

const findNodeByLabel = async (label: string): Promise<SnapshotNode | null> => {
  const snapshot = await takeSnapshot();
  return snapshot.nodes.find((node) => node.label === label) ?? null;
};

const findNodeByPartialLabel = async (
  label: string,
): Promise<SnapshotNode | null> => {
  const snapshot = await takeSnapshot();
  return snapshot.nodes.find((node) => node.label?.includes(label)) ?? null;
};

const openUrl = async (url: string, udid: string): Promise<void> => {
  if (providedUdid) {
    try {
      execFileSync("xcrun", ["simctl", "openurl", udid, url], {
        stdio: "inherit",
        timeout: 30000,
      });
    } catch (error) {
      console.warn(
        "simctl reported a URL open failure; continuing because iOS Simulator can time out after Safari has already loaded the page.",
        error,
      );
    }
    return;
  }

  try {
    await client.apps.open({
      ...deviceOptions,
      app: "Safari",
      url,
    });
  } catch (error) {
    console.warn(
      "Safari reported a URL open failure; continuing because iOS Simulator can time out after Safari has already loaded the page.",
      error,
    );
  }
};

const clickNodeCenter = async (node: SnapshotNode): Promise<void> => {
  if (node.rect) {
    await client.interactions.click({
      ...deviceOptions,
      x: node.rect.x + node.rect.width / 2,
      y: node.rect.y + node.rect.height / 2,
    });
    return;
  }

  await client.interactions.click({ ...deviceOptions, ref: `@${node.ref}` });
};

const findPartialNodeInViewport = async (
  label: string,
): Promise<SnapshotNode | null> => {
  const snapshot = await takeSnapshot();
  const viewportHeight = snapshot.nodes[0]?.rect?.height ?? 852;
  return (
    snapshot.nodes.find((node) => {
      if (!node.label?.includes(label) || !node.rect) return false;
      const centerY = node.rect.y + node.rect.height / 2;
      return centerY >= 80 && centerY <= viewportHeight - 120;
    }) ?? null
  );
};

const scrollUntilNodeInViewport = async (label: string): Promise<SnapshotNode> => {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const visibleNode = await findPartialNodeInViewport(label);
    if (visibleNode) return visibleNode;

    const node = await findNodeByPartialLabel(label);
    const viewportHeight = (await takeSnapshot()).nodes[0]?.rect?.height ?? 852;
    const centerY = node?.rect ? node.rect.y + node.rect.height / 2 : viewportHeight;
    await client.interactions.scroll({
      ...deviceOptions,
      direction: centerY > viewportHeight - 120 ? "down" : "up",
      pixels: 450,
    });
    await client.command.wait({ ...deviceOptions, durationMs: 300 });
  }

  throw new Error(`Could not bring ${label} into the viewport`);
};

const closeSessionIfPresent = async (name: string): Promise<void> => {
  try {
    const sessions = await client.sessions.list();
    if (!sessions.some((activeSession) => activeSession.name === name)) return;

    console.log(`Taking over existing agent-device session: ${name}`);
    await client.sessions.close({ session: name });
  } catch (error) {
    console.warn(`Could not check or close existing session ${name}:`, error);
  }
};

const closeDeviceSessionIfPresent = async (): Promise<void> => {
  try {
    const sessions = await client.sessions.list();
    const activeSession = sessions.find((candidate) => {
      if (providedUdid) return candidate.device.ios?.udid === providedUdid;
      return candidate.device.name === deviceName && candidate.device.platform === "ios";
    });
    if (!activeSession || activeSession.name === session) return;

    console.log(
      `Taking over iOS device from existing agent-device session: ${activeSession.name}`,
    );
    await client.sessions.close({ session: activeSession.name });
  } catch (error) {
    console.warn("Could not check or close existing device session:", error);
  }
};

const failures: string[] = [];

await closeSessionIfPresent(session);
await closeDeviceSessionIfPresent();

console.log(`Preparing iOS simulator ${providedUdid ?? deviceName}...`);
const udid = await ensureSimulator();
console.log(`Using simulator UDID: ${udid}`);

const eventUrl = `${baseUrl}${eventPath}`;
const modalUrl = `${eventUrl}?${targetQueryParam}`;
const openViaScrolledPage = env.OPEN_VIA_SCROLLED_PAGE !== "0";
console.log(`Opening Safari at ${openViaScrolledPage ? eventUrl : modalUrl}...`);
await openUrl(openViaScrolledPage ? eventUrl : modalUrl, udid);

await client.command.wait({ ...deviceOptions, durationMs: 5000 });

if (openViaScrolledPage) {
  console.log(`Opening ${targetTitle} from a scrolled page...`);
  try {
    const trigger = await scrollUntilNodeInViewport(targetTitle);
    await clickNodeCenter(trigger);
  } catch (error) {
    console.warn(
      "Could not activate the target session from the accessibility tree; opening the modal URL after the scroll attempts to keep the document in a scrolled state.",
      error,
    );
    await openUrl(modalUrl, udid);
  }
} else {
  console.log(`Waiting for ${targetTitle} details...`);
}

await client.command.wait({
  ...deviceOptions,
  selector: 'label="Close"',
  timeoutMs: 10000,
});

console.log("Checking whether modal content is initially visible...");
const contentInitiallyVisible =
  (await hasVisibleText("About this session")) &&
  (await hasVisibleText("Przygoda w stylu filmu"));
if (!contentInitiallyVisible) {
  failures.push(
    'Modal content headed by "About this session" / "Przygoda w stylu filmu" is not initially visible.',
  );
}

console.log("Tapping Close...");
const closeButton = await findNodeByLabel("Close");
if (!closeButton) {
  throw new Error('Could not find visible target: Close');
}
await clickNodeCenter(closeButton);
await client.command.wait({ ...deviceOptions, durationMs: 1000 });

if (await hasVisibleText("Close")) {
  failures.push("The modal X / Close button did not close the modal.");
}

if (failures.length > 0) {
  console.error("\nReproduced iOS modal bug(s):");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exitCode = 1;
} else {
  console.log("No iOS modal bugs reproduced.");
}
