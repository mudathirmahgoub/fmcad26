import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def plot(source_file, output):   
    # === Load CSV ===
    df = pd.read_csv(source_file)
   
    # === Filter out timeouts ===
    df_sql_solver = df[df["sqlsolver result"].astype(str).str.strip() != "timeout"]
    df_modified_sql_solver = df[(df["modified_sqlsolver result"].astype(str).str.strip() != "timeout") &
                                   (df["modified_sqlsolver result"].astype(str).str.strip() != "unknown")]
    df_unfold0 = df[df["unfold0 result"].astype(str).str.strip() != "timeout"]
    df_cvc5_lia = df[df["cvc5 result"].astype(str).str.strip() != "timeout"]
    df_unfold5 = df[df["unfold5 result"].astype(str).str.strip() != "timeout"]
    df_no_interp = df[df["no_interp result"].astype(str).str.strip() != "timeout"]

    # === Extract and sort durations ===
    column_sql_solver = df_sql_solver["sqlsolver duration"].astype(float).sort_values().tolist()
    column__modified_sql_solver = df_modified_sql_solver["modified_sqlsolver duration"].astype(float).sort_values().tolist()
    column_cvc5_lia = df_cvc5_lia["cvc5 duration"].astype(float).sort_values().tolist()
    column_unfold0 = df_unfold0["unfold0 duration"].astype(float).sort_values().tolist()    
    column_unfold5 = df_unfold5["unfold5 duration"].astype(float).sort_values().tolist()
    column_no_interp = df_no_interp["no_interp duration"].astype(float).sort_values().tolist()

    # === Compute cumulative sums ===
    sql_solver_cum = np.cumsum(column_sql_solver)
    modified_sql_solver_cum = np.cumsum(column__modified_sql_solver)
    cvc5_cum = np.cumsum(column_cvc5_lia)
    unfold0_cum = np.cumsum(column_unfold0)    
    unfold5_cum = np.cumsum(column_unfold5)
    no_interp_cum = np.cumsum(column_no_interp)

    sql_solver_x = list(range(1, len(sql_solver_cum) + 1))
    modified_sql_solver_x = list(range(1, len(modified_sql_solver_cum) + 1))
    cvc5_x = list(range(1, len(cvc5_cum) + 1))
    unfold0_x = list(range(1, len(unfold0_cum) + 1))    
    unfold5_x = list(range(1, len(unfold5_cum) + 1))
    no_interp_x = list(range(1, len(no_interp_cum) + 1))

    # === Plot ===
    plt.figure(figsize=(10, 6))

    # Accessibility: each curve uses a distinct marker shape, linestyle, and
    # colorblind-friendly color so curves remain distinguishable in greyscale
    # or for readers with color-vision deficiencies.
    plot_styles = {
        "cvc5":                            {"marker": "o", "linestyle": "-",  "color": "#0072B2"},
        "Modified SQLSolver":              {"marker": "s", "linestyle": "-", "color": "#D55E00"},
        "SLS-reachability (unfold-0)":     {"marker": "D", "linestyle": "-", "color": "#009E73"},
        "SLS-reachability (unfold-5)":     {"marker": "^", "linestyle": "-",  "color": "#CC79A7"},
        "SLS-reachability (no-interpolation)": {"marker": "v", "linestyle": "-", "color": "#E69F00"},
    }
    marker_kwargs = dict(linewidth=2, markersize=8, markevery=0.1, markeredgecolor="black", markeredgewidth=0.5)

    # plt.plot(sql_solver_cum, sql_solver_x, label="SQLSolver", **marker_kwargs)
    plt.plot(cvc5_cum, cvc5_x, label="cvc5", **plot_styles["cvc5"], **marker_kwargs)
    plt.plot(modified_sql_solver_cum, modified_sql_solver_x, label="Modified SQLSolver", **plot_styles["Modified SQLSolver"], **marker_kwargs)
    plt.plot(unfold0_cum, unfold0_x, label="SLS-reachability (unfold-0)", **plot_styles["SLS-reachability (unfold-0)"], **marker_kwargs)
    plt.plot(unfold5_cum, unfold5_x, label="SLS-reachability (unfold-5)", **plot_styles["SLS-reachability (unfold-5)"], **marker_kwargs)
    plt.plot(no_interp_cum, no_interp_x, label="SLS-reachability (no-interpolation)", **plot_styles["SLS-reachability (no-interpolation)"], **marker_kwargs)

    plt.xlabel("Cumulative time (s)",fontsize=18)
    plt.ylabel("Number of solved instances",fontsize=18)
    plt.title("Cactus Plot: Solver Performance",fontsize=18)
    plt.grid(True, linestyle="--", alpha=0.5)

    # === Magnified legend ===
    plt.legend(
        fontsize=16,        # bigger text
        markerscale=2.0,    # bigger line markers
        borderpad=1.2,      # more padding inside box
        labelspacing=1.0,   # more spacing between entries
        frameon=True,
    )

    plt.tight_layout()

    # === Save to file ===
    plt.savefig(output, dpi=300)


def scatter_plot(source_file, output, x_solver, y_solver, color, marker, timeout=100.0):
    # x_solver / y_solver: (csv column prefix, axis label)
    x_prefix, x_label = x_solver
    y_prefix, y_label = y_solver

    # === Load CSV ===
    df = pd.read_csv(source_file)

    lims = (5e-3, timeout * 2)
    edge = lims[1]  # the axis boundary -- the line that closes the box

    # Per-instance times: solved instances keep their duration (capped at
    # the timeout), timeouts sit ON the timeout line, and unknowns sit on
    # the box edge, so the two unsolved outcomes are visually distinct.
    # Solved times never exceed the timeout, so the band between the
    # timeout line and the box edge stays empty except for those markers.
    def results(prefix):
        return df[f"{prefix} result"].astype(str).str.strip().str.lower()

    def times(prefix):
        result = results(prefix)
        duration = pd.to_numeric(df[f"{prefix} duration"], errors="coerce")
        solved = duration.where(result.isin(["sat", "unsat"]), timeout)
        return solved.clip(upper=timeout).mask(result == "unknown", edge)

    x, y = times(x_prefix), times(y_prefix)
    unknown = (results(x_prefix) == "unknown") | (results(y_prefix) == "unknown")

    # === Plot ===
    plt.figure(figsize=(8, 8))
    ax = plt.gca()

    ax.scatter(x[~unknown], y[~unknown], color=color, marker=marker,
               s=25, alpha=0.7, edgecolors="black", linewidths=0.4)
    # Instances with an unknown result, drawn as their own scatter (same
    # shape as the rest for now -- change this call's marker to e.g. "x"
    # to make them distinct). clip_on lets the markers sit fully visible
    # on the box edge.
    ax.scatter(x[unknown], y[unknown], color=color, marker=marker,
               s=25, alpha=0.7, edgecolors="black", linewidths=0.4,
               clip_on=False, zorder=3)

    # Diagonal, the timeout lines and the unknown (box edge) lines
    ax.plot(lims, lims, color="gray", linestyle="--", linewidth=1, zorder=0)
    ax.axvline(timeout, color="gray", linestyle=":", linewidth=1, zorder=0)
    ax.axhline(timeout, color="gray", linestyle=":", linewidth=1, zorder=0)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_aspect("equal")

    # The timeout line and the box edge (unknown) are labeled on the
    # axes as tick labels, like the numbers. The numeric decade ticks
    # stop below the timeout (which sits at 10^2) so labels never
    # collide; the two word ticks on x are rotated to clear each other.
    decades = [10.0 ** k
               for k in range(int(np.ceil(np.log10(lims[0]))),
                              int(np.floor(np.log10(timeout))) + 1)]
    while decades and decades[-1] >= timeout:
        decades.pop()
    ticks = decades + [timeout, edge]
    from matplotlib.ticker import LogFormatterMathtext
    log_format = LogFormatterMathtext()
    labels = [log_format(d) for d in decades] \
        + ["timeout {}".format(log_format(timeout)), "unknown"]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    for label in ax.get_xticklabels()[-2:]:
        label.set_rotation(45)
        label.set_ha("right")

    ax.set_xlabel(f"{x_label} time (s)", fontsize=18)
    ax.set_ylabel(f"{y_label} time (s)", fontsize=18)
    ax.set_title(f"{x_label} vs. {y_label}", fontsize=18)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()

    # === Save to file ===
    plt.savefig(output, dpi=300)


plot("comparison.csv", "cactus_plot.png")
scatter_plot("comparison.csv", "scatter_cvc5_vs_unfold5.png",
             ("cvc5", "cvc5"), ("unfold5", "SLS-reachability (unfold-5)"),
             color="#0072B2", marker="o")
scatter_plot("comparison.csv", "scatter_cvc5_vs_modified_sqlsolver.png",
             ("cvc5", "cvc5"), ("modified_sqlsolver", "Modified SQLSolver"),
             color="#0072B2", marker="o")
