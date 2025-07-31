# Deploying Agent Zero on Railway

These instructions show how to run the framework on [Railway](https://railway.app) using the provided Dockerfile.

1. **Create a new Railway project** and link it to your fork of Agent Zero.
2. Railway automatically builds the repository using the `Dockerfile` at the root. No extra configuration is required.
3. Set any required environment variables in the Railway dashboard (for example `AUTH_LOGIN`, `AUTH_PASSWORD` or API keys). Railway provides the `PORT` variable automatically.
4. Deploy the project. Once the build completes, Railway will start the container using `run_ui.py` on the provided port.

The application will be reachable at the Railway assigned URL.
