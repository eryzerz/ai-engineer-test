# Vector DB similarity

## How to run

1. **Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Compose, and **Python 3** with `pip`.

2) **Start Qdrant:** From this directory:

```bash

docker compose up -d

```

REST API: [http://localhost:6333](http://localhost:6333) (gRPC **6334** is also exposed).

3. **Python deps:**

```bash

pip install qdrant-client

```

4. **Load demo data** (creates the `interview_demo` collection and inserts toy vectors):

```bash

python setup.py

```

5. **Run the similarity demo** (Qdrant search vs hand-rolled cosine similarity):

```bash

python main.py

```

To stop: `docker compose down`. Vector data persists under `./qdrant_data` on the host.

## Project layout

- `docker-compose.yml` — Qdrant image, ports **6333** / **6334**

- `setup.py` — connects to `http://localhost:6333`, recreates `interview_demo`, upserts sample points

- `main.py` — query Qdrant and compare scores to the cosine implementation
