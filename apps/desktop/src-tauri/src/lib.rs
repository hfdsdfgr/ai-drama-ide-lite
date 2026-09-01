use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::Manager;

#[allow(dead_code)]
struct BackendPort(Mutex<u16>);

#[allow(dead_code)]
struct BackendChild(Mutex<Option<Child>>);

#[cfg(all(not(debug_assertions), target_os = "windows"))]
fn resolve_backend_exe() -> Option<PathBuf> {
  // 安装版：后端 exe 与 app.exe 同目录；开发 release 目录没有时回退到 binaries。
  let dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
  let candidates = [
    dir.join("ai-drama-backend.exe"),
    dir.join("ai-drama-backend-x86_64-pc-windows-gnu.exe"),
  ];
  candidates.into_iter().find(|path| path.exists())
}

#[cfg(all(not(debug_assertions), target_os = "macos"))]
fn resolve_backend_exe() -> Option<PathBuf> {
  // macOS app bundle：Tauri 2 把 externalBin 放在 Contents/MacOS（与主程序同目录），
  // 旧实现只查 Contents/Resources 会找不到 sidecar，导致启动 panic 闪退。
  // 优先查主程序同目录，Resources 仅作兜底。
  let dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
  let resources = dir.join("../Resources");
  let candidates = [
    dir.join("ai-drama-backend"),
    dir.join("ai-drama-backend-aarch64-apple-darwin"),
    dir.join("ai-drama-backend-x86_64-apple-darwin"),
    resources.join("ai-drama-backend-aarch64-apple-darwin"),
    resources.join("ai-drama-backend-x86_64-apple-darwin"),
    resources.join("ai-drama-backend"),
  ];
  candidates.into_iter().find(|path| path.exists())
}

#[cfg(all(not(debug_assertions), not(any(target_os = "windows", target_os = "macos"))))]
fn resolve_backend_exe() -> Option<PathBuf> {
  None
}

#[cfg(all(not(debug_assertions), target_os = "windows"))]
fn kill_process_tree(pid: u32) {
  use std::os::windows::process::CommandExt;
  let _ = Command::new("taskkill")
    .args(["/PID", &pid.to_string(), "/T", "/F"])
    .creation_flags(0x08000000) // CREATE_NO_WINDOW
    .output();
}

#[cfg(all(not(debug_assertions), not(target_os = "windows")))]
fn kill_process_tree(pid: u32) {
  // macOS/Linux：直接结束子进程；PyInstaller onefile 的孙进程随父进程退出清理。
  let _ = Command::new("kill").args(["-9", &pid.to_string()]).status();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  #[cfg(not(debug_assertions))]
  fn find_free_port() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").expect("failed to probe free port");
    listener.local_addr().expect("failed to read port").port()
  }

  tauri::Builder::default()
    .plugin(tauri_plugin_updater::Builder::new().build())
    .plugin(tauri_plugin_process::init())
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      #[cfg(not(debug_assertions))]
      {
        let port = find_free_port();
        // 后端缺失/启动失败不允许让整个应用 panic 闪退：
        // 找不到或 spawn 失败时只记录错误，应用照常打开，由前端给出明确错误提示。
        let Some(exe) = resolve_backend_exe() else {
          log::error!("backend sidecar exe not found; app will run without backend");
          return Ok(());
        };
        let child = match Command::new(exe)
          .args(["--host", "127.0.0.1", "--port", &port.to_string()])
          .spawn()
        {
          Ok(child) => child,
          Err(err) => {
            log::error!("failed to spawn backend sidecar: {err}");
            return Ok(());
          }
        };
        app.manage(BackendPort(Mutex::new(port)));
        app.manage(BackendChild(Mutex::new(Some(child))));
        log::info!("backend sidecar started on port {}", port);
      }
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![get_backend_port])
    .build(tauri::generate_context!())
    .expect("error while building tauri application")
    .run(|app_handle, event| {
      if let tauri::RunEvent::Exit = event {
        #[cfg(not(debug_assertions))]
        {
          if let Some(mut child) = app_handle
            .try_state::<BackendChild>()
            .and_then(|state| state.0.lock().unwrap().take())
          {
            let pid = child.id();
            // 先杀整棵进程树（父进程仍活着时 /T 才能枚举到子进程），再兜底杀父。
            kill_process_tree(pid);
            let _ = child.kill();
          }
        }
      }
    })
}

#[tauri::command]
fn get_backend_port(app: tauri::AppHandle) -> Option<u16> {
  app
    .try_state::<BackendPort>()
    .map(|state| state.0.lock().unwrap().clone())
}
