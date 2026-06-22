# Roast My Startup

Roast My Startup is a local-first multi-agent critique app. A user submits a startup idea, five AI judges evaluate it from different lenses, then the judges debate each other before a moderator produces a final synthesis.

The app is built for learning and experimentation with LangGraph, LangChain, local Ollama models, and the DeepAgents SDK. The production path is intentionally deterministic because local tool-calling models can be inconsistent when asked to orchestrate multi-agent work on their own.

## Screenshots

![Roast Panel main page](images/Roast%20Panel%20Main%20Page.png)

| Individual verdicts | Judge scores radar |
| --- | --- |
| ![Judge verdicts](images/Judge%20Verdicts.png) | ![Judge scores radar](src/roast_radar.png) |

| Debate round 1 | Debate round 2 | Debate round 3 |
| --- | --- | --- |
| ![Debate round 1](images/Debate%20Round%201.png) | ![Debate round 2](images/Debate%20Round%202.png) | ![Debate round 3](images/Debate%20Round%203.png) |

| Final synthesis | Appeal mode | After appeal synthesis |
| --- | --- | --- |
| ![Final synthesis](images/Final%20Synthesis.png) | ![Appeal mode](images/Appeal%20Mode.png) | ![After appeal synthesis](images/After%20Appeal%20Synthesis.png) |


## What It Does

- Runs five independent judge evaluations in parallel:
  - VC
  - Engineer
  - Product Manager
  - Customer
  - Competitor
- Produces structured verdicts with score, pass/fail/conditional label, roast, and key concern.
- Runs a LangGraph debate where every judge speaks in a fixed order for configurable rounds.
- Produces a final moderator synthesis.
- Remembers prior ideas for the current user and injects compact memory into future judge prompts.
- Supports Appeal Mode, where the founder can argue back and the judges re-evaluate their scores.
- Exports transcripts to Markdown.
- Renders a radar chart for judge scores.

## Architecture

The current app has two distinct paths:

1. Production path: deterministic pipeline
2. Experimental path: DeepAgents orchestrator

The deterministic path is the one used by the Streamlit app:

```text
User idea
  -> Phase 1: parallel structured judge calls
  -> Phase 2: LangGraph debate graph
  -> Moderator synthesis
  -> Optional Appeal Mode
  -> Persist idea memory
```

This is the practical choice for local models. The app needs all five judges to speak, predictable debate rounds, and validated structured output. Those guarantees are easier to enforce with direct model calls plus LangGraph than with an LLM-planned DeepAgents orchestrator.

DeepAgents still exists in `src/orchestrator/deep_agent.py` as an experimental path for learning subagent dispatch through `task()`. It is useful when trying stronger tool-calling models, but it is not the default user-facing path.

## Key Design Choices

### Deterministic orchestration over agent autonomy

The debate is a product workflow, not an open-ended agent task. LangGraph owns the state machine and turn routing, so the app can guarantee that each judge speaks in each round.

### Structured output at the boundary

Judge results are validated with Pydantic models in `src/judges/schemas.py`. This keeps downstream debate, charts, memory, and exports working with predictable data.

### Memory is compact, not transcript-heavy

Memory is stored durably in SQLite, but prompts only receive a short summary of prior ideas, score trends, concerns, and synthesis. Full debate transcripts are intentionally not injected into every judge prompt because local models have limited context and can drift when overloaded.

### Appeal Mode is a third phase

Appeal Mode does not rerun the whole debate by default. It sends the founder's rebuttal to each judge, asks them to revise or defend their original verdict, then synthesizes what changed.

## Repository Layout

```text
src/
  app.py                         Streamlit app entry point
  pipeline.py                    Frontend-agnostic production pipeline
  config.py                      Model and app settings

  judges/
    schemas.py                   Pydantic verdict models
    service.py                   Single judge structured evaluation
    panel.py                     Parallel five-judge panel

  debate/
    graph.py                     LangGraph debate definition
    nodes.py                     Speaker and moderator nodes
    router.py                    Turn routing and round advancement
    state.py                     Debate state schema

  memory/
    models.py                    Persisted idea record model
    store.py                     SQLite-backed idea store
    context.py                   Compact prompt context builder

  appeal/
    service.py                   Appeal re-evaluation and synthesis

  orchestrator/
    deep_agent.py                Experimental DeepAgents orchestrator

  ui/
    streamlit_runner.py          Streamlit adapters for event streams

  utils/
    roast_panel_parser.py        DeepAgents result parser fallback
    scoring_chart.py             Radar chart generation
    transcript_exporter.py       Markdown transcript export

tests/
  test_*.py                      Unit tests using unittest
```

## Requirements

- Python 3.11+
- Ollama installed and running
- A local chat model available through Ollama

Install dependencies:

```bash
pip install -r requirements.txt
```

Pull a local model. The default in `src/config.py` is:

```bash
ollama pull qwen3.5:9b
```

If you use a different model, set it in `.env`:

```bash
LOCAL_MODEL=ollama:qwen3.5:9b
MAX_DEBATE_ROUNDS=3
```

Use a model with decent structured-output and instruction-following behavior. Local models vary a lot here. If judge outputs fail validation, try a stronger tool-calling/instruct model.

## Run The App

Start the Streamlit app:

```bash
streamlit run src/app.py
```

Then:

1. Enter a startup idea.
2. Click `Roast It!`.
3. Review individual verdicts, score chart, debate transcript, and final synthesis.
4. Use Appeal Mode to argue back with concrete evidence.
5. Download the transcript if needed.

## Memory

The app stores idea memory in:

```text
data/ideas.db
```

Memory is scoped to the Streamlit session user id. A new browser/session gets a new local user id unless you change the identity logic in `src/app.py`.

The memory prompt context is built in `src/memory/context.py`. It deliberately summarizes:

- prior idea text
- average score
- top judge concerns
- previous synthesis
- prior appeal outcome, if present

It does not inject full transcripts.

## Appeal Mode

Appeal Mode lives in `src/appeal/service.py`.

The founder's appeal is sent to all five judges with:

- original startup idea
- original verdict for that judge
- original moderator synthesis
- optional compact memory context
- appeal text

Each judge returns a fresh validated `Verdict`. The UI shows revised scores and score deltas against the original panel.

Good appeals should include evidence, not just persuasion. For example:

```text
We already have three signed LOIs worth $180k ARR and two hospital pilots.
The buyer is the compliance VP, not clinicians, and budget comes from existing audit spend.
```

## Testing

Run the full test suite:

```bash
python -m unittest discover -s tests
```

Compile-check source files:

```bash
python -m compileall src
```

The tests use fake models where possible so they do not require Ollama.

## Generated Files

The app may generate local runtime artifacts:

```text
data/ideas.db
transcripts/*.md
roast_radar.png
```

These are runtime outputs, not source code. Keep them out of commits unless you intentionally want sample artifacts.

## Versioning And CI

**App version** lives in `pyproject.toml` under `[project].version`. Runtime code reads it via `src/version.py` — do not duplicate the string elsewhere.

**Dependencies** are pinned in `requirements.txt` for reproducible installs and CI. When upgrading a library, bump the pin, run tests, and commit both files if needed.

**Releases** use [Semantic Versioning](https://semver.org/):

1. Bump `version` in `pyproject.toml` (e.g. `0.1.0` → `0.2.0`).
2. Run tests locally.
3. Commit, tag `v0.2.0`, and push the tag.
4. Create a GitHub Release from that tag with release notes.

CI (`.github/workflows/ci.yml`) runs on every push and pull request to `main`: installs pinned deps, verifies the version resolves, runs unit tests, and compile-checks `src/`.

## Notes For Maintainers

- Keep the production path deterministic unless there is a strong reason not to.
- Treat `src/orchestrator/deep_agent.py` as experimental until local model tool-calling is reliable enough to dispatch all judge subagents consistently.
- Prefer adding small frontend-agnostic services first, then adapting them into Streamlit.
- Keep prompts short and specific. Local models degrade quickly when given long transcripts plus complex instructions.
- Preserve the Pydantic schemas as the contract between phases.
- When adding new features, add tests around the service layer before wiring UI.

## Current Limitations

- Memory identity is session-local, not account-based.
- Appeal Mode re-evaluates judges but does not run a second multi-round debate.
- SQLite storage is local-only.
- Streamlit is the primary UI; there is no separate CLI entry point for the full memory/appeal flow yet.
- DeepAgents support is present for experimentation but not trusted as the production orchestrator.