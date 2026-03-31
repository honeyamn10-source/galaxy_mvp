#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;

use tauri::{CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu};

const DASHBOARD_URL: &str = "http://localhost:8000";

fn run_shell(command: &str) -> Result<(), String> {
  let status = if cfg!(target_os = "macos") || cfg!(target_os = "linux") {
    Command::new("sh")
      .arg("-lc")
      .arg(command)
      .status()
      .map_err(|e| format!("failed to execute shell: {e}"))?
  } else {
    return Err("unsupported desktop OS".into());
  };

  if status.success() {
    Ok(())
  } else {
    Err(format!("command failed with status: {status}"))
  }
}

fn ensure_docker_running() -> Result<(), String> {
  run_shell("docker info >/dev/null 2>&1")
}

fn start_stack_inner() -> Result<String, String> {
  ensure_docker_running()?;
  run_shell("cd /home/honey/mvp && docker compose up -d")?;
  Ok("Galaxy stack started".into())
}

fn stop_stack_inner() -> Result<String, String> {
  ensure_docker_running()?;
  run_shell("cd /home/honey/mvp && docker compose down")?;
  Ok("Galaxy stack stopped".into())
}

#[tauri::command]
fn start_stack() -> Result<String, String> {
  start_stack_inner()
}

#[tauri::command]
fn stop_stack() -> Result<String, String> {
  stop_stack_inner()
}

#[tauri::command]
fn open_dashboard(app: tauri::AppHandle) -> Result<(), String> {
  tauri::api::shell::open(
    &app.shell_scope(),
    DASHBOARD_URL.to_string(),
    None,
  )
  .map_err(|e| format!("failed to open dashboard: {e}"))
}

fn main() {
  let start_item = CustomMenuItem::new("start".to_string(), "Start Stack");
  let stop_item = CustomMenuItem::new("stop".to_string(), "Stop Stack");
  let open_item = CustomMenuItem::new("open".to_string(), "Open Dashboard");
  let quit_item = CustomMenuItem::new("quit".to_string(), "Quit");

  let tray_menu = SystemTrayMenu::new()
    .add_item(start_item)
    .add_item(stop_item)
    .add_item(open_item)
    .add_item(quit_item);
  let tray = SystemTray::new().with_menu(tray_menu);

  tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![start_stack, stop_stack, open_dashboard])
    .setup(|_app| {
      let _ = start_stack_inner();
      Ok(())
    })
    .system_tray(tray)
    .on_system_tray_event(|app, event| {
      if let SystemTrayEvent::MenuItemClick { id, .. } = event {
        match id.as_str() {
          "start" => {
            let _ = start_stack_inner();
          }
          "stop" => {
            let _ = stop_stack_inner();
          }
          "open" => {
            let _ = tauri::api::shell::open(&app.shell_scope(), DASHBOARD_URL.to_string(), None);
          }
          "quit" => {
            app.exit(0);
          }
          _ => {}
        }
      }
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
