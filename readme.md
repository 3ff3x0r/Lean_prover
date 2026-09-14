# Lean 4 Proof Automation Agent

A modular, model-agnostic proof automation framework that bridges natural-language mathematical statements and formally verified Lean 4 proofs.

The system uses a local LLM to generate and repair Lean code, while **Lean 4 + Mathlib remain the final authority for proof certification**. Rather than trusting the language model's output, the agent treats proof generation as a search problem guided by kernel feedback.

The current architecture consists of three main passes:

1. **Formalization:** Convert a natural-language theorem statement into a structured Lean declaration.
2. **Kernel Initialization:** Instantiate the formal theorem in a temporary Lean environment and obtain its initial proof state.
3. **Multi-Candidate Proof Search:** Generate multiple candidate proof scripts, verify each against the Lean kernel, and use kernel errors to guide subsequent search.

The architecture is designed to be **model-agnostic**, allowing different local or OpenAI-compatible LLM backends to be used without changing the proof-search or verification layers.

---

## Architecture Overview

### Pass 1: Formalization

The natural-language mathematical statement is sent to the configured LLM with a structured output schema.

The model produces the components required to instantiate the theorem:

```text
Natural-language statement
        │
        ▼
      Local LLM
        │
        ▼
Structured JSON
 ┌───────────────┐
 │ params        │
 │ proposition   │
 └───────────────┘
        │
        ▼
Validated Lean declaration
```

The output is treated as a formalization candidate rather than as a proof. Its purpose is to establish the Lean-level theorem statement that will subsequently be passed to the kernel.

---

### Pass 2: Kernel Initialization

The formalized theorem is written to a temporary Lean scratchpad, currently:

```text
interactive_proof.lean
```

The agent then launches the `lean4-repl` process through `lake` and obtains the initial Lean proof state.

Conceptually, the transition is:

```text
Formal theorem declaration
        │
        ▼
interactive_proof.lean
        │
        ▼
lean4-repl
        │
        ▼
Initial goal state
        │
        └── ⊢ proposition
```

This establishes the actual proof state that the search procedure must solve.

The important design principle is that the agent does not attempt to independently determine whether a generated proof is valid. **Every candidate is evaluated by Lean itself.**

---

### Pass 3: Multi-Candidate BFS Search and Repair

The proof-search layer generates a batch of candidate Lean proof scripts.

For a search batch of size `k`, the LLM produces up to `k` distinct candidate continuations. Each candidate is submitted to the Lean kernel and classified according to its result.

A successful candidate must satisfy the certification condition:

```text
0 kernel errors
0 `sorry` declarations
```

Failed candidates are retained together with their kernel error messages. These errors become part of the attempt history supplied to subsequent generations.

The resulting process can be summarized as:

```text
                    ┌──────────────────────────────┐
                    │ PASS 3: Multi-Candidate BFS  │
                    │                              │
                    │ Generate k proof candidates  │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      LEAN KERNEL             │
                    │      VERIFICATION            │
                    └──────────────┬───────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
                     ▼                           ▼
              ┌───────────────┐         ┌──────────────────┐
              │   Certified   │         │ Kernel Rejection │
              │               │         │                  │
              │ 0 errors      │         │ Error message    │
              │ 0 `sorry`s    │         │ + candidate      │
              └───────┬───────┘         └────────┬─────────┘
                      │                          │
                      ▼                          ▼
                 SUCCESS                 Attempt History
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │ More candidates/depth? │
                                    └───────────┬────────────┘
                                                │
                              ┌─────────────────┴─────────────────┐
                              │                                   │
                             Yes                                  No
                              │                                   │
                              ▼                                   ▼
                       Test next branch                       Terminate
                              │
                              └──────────────► Search
```

The search therefore combines LLM generation with deterministic formal verification. The LLM proposes possible proofs, while Lean determines which proposals are actually valid.

---

## System Architecture

The complete execution pipeline is:

```text
┌─────────────────────────────┐
│ Natural Language Theorem    │
│ Statement                   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ PASS 1: Formalization       │
│                             │
│ translator.py               │
│                             │
│ Natural Language → JSON     │
│ params + proposition        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Validated Lean Declaration  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ PASS 2: Kernel Initialization│
│                             │
│ repl_bridge.py / agent.py   │
│                             │
│ Create scratchpad           │
│ Spawn lean4-repl            │
│ Extract initial goal state  │
└──────────────┬──────────────┘
               │
               ▼
        ┌───────────────┐
        │      ⊢        │
        │ Initial Goal  │
        └───────┬───────┘
                │
                ▼
┌─────────────────────────────┐
│ PASS 3: BFS Proof Search    │
│                             │
│ tactic_generator.py         │
│                             │
│ Generate k candidates       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Lean Kernel Verification    │
│                             │
│ lean4-repl subprocess       │
└──────────────┬──────────────┘
               │
        ┌──────┴───────┐
        │              │
        ▼              ▼
   Certified        Rejected
        │              │
        │              ▼
        │       Capture kernel
        │       error + candidate
        │              │
        │              ▼
        │       Append to history
        │              │
        │              ▼
        │       Continue search
        │
        ▼
  Certified Proof
```

---

## Project Structure

```text
MathProofs/
├── config.py                 # Centralized runtime configuration
├── llm_client.py             # HTTP interface to the local LLM server
├── translator.py             # Pass 1: Natural language → formal AST
├── repl_bridge.py             # Pass 2: Lean REPL process manager
├── tactic_generator.py        # Pass 3: Multi-candidate BFS proof search
├── agent.py                   # End-to-end supervisor
└── interactive_proof.lean     # Temporary Lean verification target
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Runtime paths, endpoints, model configuration, and search parameters |
| `llm_client.py` | Communication with the configured LLM backend |
| `translator.py` | Converts natural-language statements into structured Lean declarations |
| `repl_bridge.py` | Manages the `lean4-repl` subprocess and parses its responses |
| `tactic_generator.py` | Generates and manages multiple proof candidates |
| `agent.py` | Coordinates formalization, kernel initialization, search, repair, and termination |
| `interactive_proof.lean` | Scratchpad used for kernel-level verification |

---

## Verification Model

The project deliberately separates **generation** from **certification**.

The LLM is responsible for proposing:

```text
Theorem formalizations
Proof scripts
Proof repairs
```

Lean is responsible for determining:

```text
Whether the formal statement is syntactically valid
Whether tactics elaborate successfully
Whether generated terms satisfy the required types
Whether the resulting proof closes the goal
```

Consequently, an LLM response is never considered a successful proof merely because it appears mathematically plausible.

The certification boundary is:

```text
LLM
 │
 │ generates candidate
 ▼
Lean elaborator / kernel
 │
 ├── reject → search continues
 │
 └── accept → certified proof
```

This makes the LLM a heuristic search component rather than a trusted component of the proof system.

---

## Search Strategy

The proof generator uses a breadth-first, multi-candidate search strategy.

At each search stage, the system can generate multiple possible proof continuations:

```text
                    Current Goal
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
           Proof A    Proof B    Proof C
              │          │          │
              ▼          ▼          ▼
           Lean       Lean       Lean
              │          │          │
            fail       fail       fail
              │          │          │
              └──────────┼──────────┘
                         │
                  Kernel feedback
                         │
                         ▼
                  Next search layer
```

This provides several advantages over repeatedly requesting a single proof from the model:

- Multiple hypotheses can be explored simultaneously.
- A failed proof attempt provides concrete kernel feedback.
- Search can recover from locally incorrect tactic choices.
- The model does not need to produce the complete proof in a single generation.
- Proof discovery is separated from proof certification.

The attempt history can contain both successful and unsuccessful branches, allowing subsequent candidates to be conditioned on previous kernel feedback.

---

## Requirements

The project currently assumes the following components are available locally.

### Lean 4 and Mathlib

Install Lean 4 and Mathlib using `elan` and `lake`.

The project expects a working Lean development environment capable of compiling the target theorem and importing the required Mathlib modules.

### lean4-repl

The agent requires a locally built `lean4-repl` executable.

The expected executable path follows the project structure:

```text
.lake/packages/repl/.lake/build/bin/repl
```

### Local LLM Server

A local LLM server must expose an OpenAI-compatible chat-completions endpoint.

The current configuration is designed to work with servers such as `llama.cpp`, although the HTTP abstraction is intended to remain model- and backend-agnostic.

---

## Installation and Configuration

Clone the repository and place the project in the desired working directory.

Configure the local paths and LLM endpoint in `config.py`.

For example:

```python
CWD = "/path/to/MathProofs"

REPL_BIN = os.path.join(
    CWD,
    ".lake/packages/repl/.lake/build/bin/repl"
)

LAKE_BIN = "/home/username/.elan/bin/lake"

LLM_URL = "http://127.0.0.1:11434/v1/chat/completions"

MODEL_NAME = "your-local-model-identifier"
```

The exact values depend on the local installation.

Before running the agent, verify that:

1. Lean 4 is available.
2. Mathlib is correctly installed.
3. `lake` can build the project.
4. `lean4-repl` has been built.
5. The configured LLM server is running.
6. The configured model is available through the LLM endpoint.

---

## Usage

The supervisor agent can be invoked from the command line with a natural-language theorem statement:

```bash
python agent.py --debug \
    "Prove that there is the same number of even and odd numbers"
```

The `--debug` option enables additional diagnostic output from the execution pipeline.

Conceptually, the command performs:

```text
Natural-language theorem
        │
        ▼
Formalization
        │
        ▼
Lean theorem initialization
        │
        ▼
Initial proof state
        │
        ▼
Candidate generation
        │
        ▼
Kernel verification
        │
        ├── failure → feedback → next candidates
        │
        └── success → certified proof
```

---

## Design Principles

### 1. Kernel Verification Over Model Confidence

The language model is not trusted to determine whether a proof is correct.

A candidate is successful only when Lean accepts it.

### 2. Model Agnosticism

The proof-search architecture should not depend on the internal architecture of a particular LLM.

The model is accessed through an HTTP interface, allowing different local models or compatible inference servers to be substituted.

### 3. Search Rather Than Single-Shot Generation

Mathematical proof generation is treated as a search problem.

Instead of assuming that the first generated proof is correct, the agent maintains multiple candidates and uses formal feedback to eliminate unsuccessful branches.

### 4. Explicit Error Feedback

Lean kernel and elaboration errors are valuable search information.

Instead of discarding failed attempts, the system records the candidate and its associated error so that subsequent generation can take previous failures into account.

### 5. Separation of Concerns

The architecture separates:

```text
Natural-language understanding
          ↓
Formal theorem construction
          ↓
Proof-state initialization
          ↓
Proof search
          ↓
Formal verification
```

This allows individual components to be developed and evaluated independently.

---

## Current Scope

The current implementation focuses on theorem proving in Lean 4 using Mathlib and a local LLM.

The main research and engineering questions include:

- How effectively can multi-candidate search improve proof success?
- How much useful information is contained in Lean's error messages for proof repair?
- How does search breadth affect proof-discovery rate?
- How does model choice affect formalization and proof-generation quality?
- Can local models perform competitively with larger hosted models when combined with structured search?
- Which classes of mathematical statements benefit most from kernel-guided search?

---

## Conceptual Model

The system can be viewed as a hybrid symbolic-neural architecture:

```text
              ┌─────────────────────┐
              │      Human / User    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │       LLM           │
              │                     │
              │ Heuristic Generator │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │     Lean 4          │
              │                     │
              │ Formal Verifier     │
              └──────────┬──────────┘
                         │
                  ┌──────┴──────┐
                  │             │
                  ▼             ▼
               Reject         Accept
                  │             │
                  │             ▼
                  │       Certified Proof
                  │
                  ▼
             Search Feedback
                  │
                  └──────────────► LLM
```

The central idea is therefore not to make the LLM itself a trusted theorem prover. Instead, the LLM supplies heuristic proposals to a formal proof system, while the Lean kernel provides the definitive correctness criterion.

---

## Status

This project is an experimental proof-automation framework.

The current implementation establishes the basic pipeline:

```text
Natural Language
      ↓
Formalization
      ↓
Lean Goal
      ↓
Multi-Candidate Search
      ↓
Kernel Verification
      ↓
Certified Proof
```

Further development is focused on improving search efficiency, proof repair, candidate diversity, and evaluation across different classes of mathematical problems.