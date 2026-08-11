const fs = require("fs");
const http = require("http");
const { spawn } = require("child_process");
const path = require("path");

const [, , viewLabel = "Trabajo Ágil", outPath = "docs/manual/assets/03-scrum.png"] = process.argv;
const chrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const userDataDir = path.join(process.cwd(), ".tmp-chrome-manual-shot");
const out = path.resolve(process.cwd(), outPath);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = "";
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => resolve(JSON.parse(body)));
    }).on("error", reject);
  });
}

async function waitForTabs(port) {
  for (let i = 0; i < 50; i += 1) {
    try {
      return await getJson(`http://127.0.0.1:${port}/json`);
    } catch {
      await sleep(200);
    }
  }
  throw new Error("Chrome DevTools did not start");
}

async function send(ws, method, params = {}) {
  const id = (ws._id || 0) + 1;
  ws._id = id;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    const handler = (event) => {
      const msg = JSON.parse(event.data.toString());
      if (msg.id !== id) return;
      ws.removeEventListener("message", handler);
      if (msg.error) reject(new Error(JSON.stringify(msg.error)));
      else resolve(msg.result || {});
    };
    ws.addEventListener("message", handler);
  });
}

async function main() {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.rmSync(userDataDir, { recursive: true, force: true });
  const port = 9227;
  const proc = spawn(chrome, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "--window-size=1440,1100",
    "about:blank",
  ], { stdio: "ignore" });

  try {
    const tabs = await waitForTabs(port);
    const target = tabs.find((tab) => tab.type === "page") || tabs[0];
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    ws._id = 0;
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve);
      ws.addEventListener("error", reject);
    });
    await send(ws, "Page.enable");
    await send(ws, "Runtime.enable");
    await send(ws, "Page.navigate", { url: "http://127.0.0.1:8000" });
    await sleep(2500);
    await send(ws, "Runtime.evaluate", {
      awaitPromise: true,
      expression: `
        (() => {
          const email = document.querySelector('input[type="email"], input[name="email"]');
          const pass = document.querySelector('input[type="password"], input[name="password"]');
          if (!email || !pass) return;
          const set = (el, value) => {
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(el, value);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
          };
          set(email, 'alejandra@proyecta360.ai');
          set(pass, 'demo123');
          const button = [...document.querySelectorAll('button')].find((item) => /Ingresar|Login|Sign in/i.test(item.textContent)) || document.querySelector('button[type="submit"]');
          if (button) button.click();
        })();
      `,
    });
    await sleep(3000);
    await send(ws, "Runtime.evaluate", {
      awaitPromise: true,
      expression: `
        (() => {
          const label = ${JSON.stringify(viewLabel)};
          const button = [...document.querySelectorAll('button')].find((item) => (item.textContent || item.getAttribute('aria-label') || '').includes(label));
          if (button) button.click();
        })();
      `,
    });
    await sleep(1500);
    const visible = await send(ws, "Runtime.evaluate", {
      returnByValue: true,
      expression: `
        ({
          ok: document.body.innerText.includes(${JSON.stringify(viewLabel)}),
          text: document.body.innerText.slice(0, 500)
        })
      `,
    });
    if (!visible.result?.value?.ok) {
      throw new Error(`Target view was not visible: ${visible.result?.value?.text || ""}`);
    }
    const metrics = await send(ws, "Page.getLayoutMetrics");
    const contentSize = metrics.contentSize;
    const shot = await send(ws, "Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: Math.min(contentSize.width, 1440), height: Math.min(contentSize.height, 1800), scale: 1 },
    });
    fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
    ws.close();
    console.log(out);
  } finally {
    proc.kill();
    await sleep(500);
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
