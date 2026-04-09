module.exports = {
  apps: [
    {
      name: "idim-scanner",
      cwd: "./observer_bundle",
      script: "python3",
      args: "scanner.py",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "idim-api",
      cwd: "./observer_bundle",
      script: "python3",
      args: "-m uvicorn api:app --host 0.0.0.0 --port 8787",
      interpreter: "none",
      autorestart: true,
      watch: false,
      ignore_watch: ["logs", "*.log", "node_modules", "__pycache__"],
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "idim-outcome-tracker",
      cwd: "./observer_bundle",
      script: "python3",
      args: "outcome_tracker.py --loop",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "idim-auto-executor",
      cwd: "./observer_bundle",
      script: "python3",
      args: "auto_executor.py",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
}
