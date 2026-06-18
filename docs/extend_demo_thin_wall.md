# Extend mode on a *tightly-scoped* question — a worked demo

The paper-extend mode (`doktores.extend`) normally takes a whole manuscript and surfaces the
questions it does not ask. This demo shows a second use: scope the "paper" down to **one
narrow open question** and let the unusual-method library probe *that*. What survives the
Doktoren triage is the apparatus's answer.

It is also the clearest example we have of the acceptance criterion in action (see
`CLAUDE.md` → *Paper modes*): the run produced something the operator, reasoning by hand,
had gotten *subtly backwards* — i.e. the scaffold beat the naked model on a real point.

## The question

> Does thinning the Alcubierre warp-bubble wall reduce the energy requirement?

Standard analysis says no: the Eulerian energy density is

```
rho_E = -(c^4 / 8 pi G) * (v_s^2 (y^2 + z^2) / 4 r_s^2) * (df/dr_s)^2
```

For a wall of radius `R` and thickness `Δ`, `(df/dr_s)^2 ~ 1/Δ^2` over a shell of volume
`~ R^2 Δ`, so the total `|E| ~ v_s^2 R^2 / Δ` **diverges** as `Δ → 0`; the Ford–Roman /
Pfenning quantum inequality `|E| τ^4 ≲ ℏ` then pushes the wall toward Planck thickness and
the total negative energy toward astronomical mass. The run was fed these competing
positions as claims/sections and asked to find any escape.

Single strong model (Claude Opus 4.8), `max_questions=10`. Triage: **7 present / 3 discard**.

## Kevin's answer — four methods converge on one diagnosis

The 1/Δ divergence is real but is **partly an artifact of two modelling choices**, not an
absolute:

1. **Bulk field vs. surface** (`limit_case_analysis`, `dimensional_consistency`). The 1/Δ
   comes from integrating `(df/dr_s)^2` over a *volume*. Treat the wall instead as a literal
   **Israel thin shell** — a distributional surface layer with finite surface stress-energy
   `σ` from the junction conditions — and `σ` stays *finite* as `Δ → 0`.
   `dimensional_consistency` sharpens it: the divergent quantity is an *extensive bulk
   energy*, while the quantum inequality bounds a *local sampled density* — different kinds.
   Rewritten as a per-unit-area surface tension (with `R ~ Δ^{1/2}` holding `R^2/Δ` fixed),
   the area term can stay finite while the bulk integral diverges. This does not remove the
   exotic matter (`σ` is still negative-tension); it moves the bookkeeping from "divergent"
   to "finite but exotic" — which is essentially what Bobrick–Martire do with shells.

2. **The optimisation is over the wrong variable** (`invert_then_flip`). `Δ` is not a free
   parameter to send to zero; it is the *output* of a constrained variational problem —
   minimise `∫ rho_E` subject to a fixed Ford–Roman sampling-time budget (Lagrange
   multiplier). The optimum then sits at a **finite `Δ* ≠ 0`**; the 1/Δ divergence is an
   artifact of optimising the wrong constrained variable.

3. **Which observer measures the divergence?** (`first_principles_reduction`) — *this is the
   one that corrected the operator.* The divergence lives in the **Eulerian** density (a
   static-observer congruence). The observer who actually meets the quantum-inequality bound
   is the **payload crossing the wall**, with proper sampling time `τ ~ Δ/v`:

   - allowed density: `|⟨ρ⟩| ≲ ℏ/τ^4 ~ ℏ v^4 / Δ^4`
   - actual local density: `rho_E ~ v_s^2 / Δ^2`
   - ratio actual/allowed `~ v_s^2 Δ^2 / v^4 → 0` as `Δ → 0`

   So for the fast-crossing observer a *thinner* wall satisfies the quantum inequality **more
   easily**, not less — short `τ` *relaxes* the bound. (The hand-written explanation this run
   was checked against had blurred that direction.)

**Honest caveat — the human-review part the rule does not supply.** The quantum inequality
must hold for *all* geodesic observers, including one at rest relative to the wall who
samples it over long `τ`; for that observer the bound stays lethal, and Pfenning–Ford's
"Planck-thin wall + galactic mass" uses exactly such a long-sampling observer. So the
payload angle does **not** refute the lethal verdict — it shows the verdict is
**observer- and framing-dependent**, not absolute. Bottom line: thinning is not monotonically
cheaper (1/Δ in the bulk picture; finite optimum `Δ*`), but "thin = automatically lethal" is
a property of the static-Eulerian, bulk-energy framing — as an Israel shell and from the
crossing payload's frame, the thin-wall limit is markedly friendlier than the standard
calculation suggests.

## What the triage discarded (correctly)

- `conservation_tracking` — an ADM charge "flowing into the Van Den Broeck pocket"; energy
  is not conserved that way *between distinct metrics*. (Discarded in three physics-adjacent
  runs in a row — a stable signal that this method tends to the contrived.)
- `structural_analogy_transport` — a Gibbs dividing-surface analogy, redundant with the
  surface-tension reframing above.
- `emergence_search` — the wall as a lattice of bits, `|E|` as an information-localisation
  cost; decorative here.

## Why this demo matters

It is the cleanest instance of the mode's reason to exist: a *forced* Denkbewegung
(`first_principles_reduction`: "who is the actor that measures this?") produced a correct,
non-obvious point that the operator's by-hand reasoning had gotten subtly wrong — i.e.
*author-surprising-but-true*, the only metric that counts. And the cross-domain method
profile held: `dimensional_consistency` and `invert_then_flip` carried again; the decorative
methods were correctly triaged out.
</content>
