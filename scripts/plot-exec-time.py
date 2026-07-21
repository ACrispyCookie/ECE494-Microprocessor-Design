import matplotlib.pyplot as plt
import numpy as np

def plot_execution_time_change(f_base_hz, f_new_hz, base_cpi=1.0):
    """
    Plots the % change in execution time of the new design vs. the baseline
    and saves the output as a PNG file.
    
    Parameters:
    f_base_hz (float): Baseline frequency in Hz (e.g., 50_000_000 for 50 MHz).
    f_new_hz (float): New frequency in Hz (e.g., 55_000_000 for 55 MHz).
    base_cpi (float): The baseline Cycles Per Instruction (default is 1.0).
    """
    
    # Create an array of potential MUL dependency percentages from 0% to 15%
    x_pct = np.linspace(0, 15, 200)
    
    # 1. Calculate New CPI for the entire array
    # Every 1% of MUL dependency adds 0.01 to the CPI (due to the 1-cycle stall)
    cpi_new = base_cpi + (x_pct / 100)
    
    # 2. Calculate Execution Time Ratio: (CPI_new / CPI_base) * (F_base / F_new)
    # Note: Instruction count cancels out!
    time_ratio = (cpi_new / base_cpi) * (f_base_hz / f_new_hz)
    
    # 3. Convert to Percentage Change (+ means slower, - means faster)
    exec_time_change_pct = (time_ratio - 1) * 100

    # --- Print the execution time change at 0.0% dependency ---
    change_at_zero_pct = ((f_base_hz / f_new_hz) - 1) * 100
    print(f"Execution time change at 0.0% dependency: {change_at_zero_pct:+.2f}%")
    # -----------------------------------------------------------------------------

    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot the main trend line
    ax.plot(x_pct, exec_time_change_pct, color='black', linewidth=2, zorder=3)
    
    # Add a break-even horizontal line at 0%
    ax.axhline(0, color='gray', linestyle='--', linewidth=1.5, zorder=2)
    
    # Fill areas to show "Faster" vs "Slower"
    ax.fill_between(x_pct, exec_time_change_pct, 0, where=(exec_time_change_pct < 0), 
                    color='green', alpha=0.2, label='Faster')
    ax.fill_between(x_pct, exec_time_change_pct, 0, where=(exec_time_change_pct > 0), 
                    color='red', alpha=0.2, label='Slower')
    
    # Capture Y-axis limits early so we can anchor our vertical lines to the absolute bottom
    ymin, ymax = ax.get_ylim()
                    
    # Lock y-axis limits, adding a bit of headroom for text
    ax.set_ylim(ymin, ymax * 1.15) 

    # --- PLOTTING THE BENCHMARK DOTS ---
    mm_dep_pct = ((18353 - 16625) / 16625) * 100
    multiply_dep_pct = ((2246 - 2086) / 2086) * 100

    benchmarks = [
        {"name": "vvadd, median,\nsort, rsort,\ndhrystone", "dep": 0.0},
        {"name": "multiply", "dep": multiply_dep_pct},
        {"name": "mm", "dep": mm_dep_pct}
    ]

    for bench in benchmarks:
        # Calculate exactly where this benchmark sits on the Y-axis (Execution Time Change %)
        cpi = base_cpi + (bench["dep"] / 100)
        ratio = (cpi / base_cpi) * (f_base_hz / f_new_hz)
        y_val = (ratio - 1) * 100

        # Plot the dot
        ax.scatter([bench["dep"]], [y_val], color='black', s=50, edgecolor='white', zorder=7)
        
        # Align the 0% text to the left so it doesn't clip off the screen
        align = 'left' if bench["dep"] == 0 else 'center'
        x_offset = 5 if bench["dep"] == 0 else 0
        
        # Annotate the benchmark name above the dot
        ax.annotate(bench["name"], xy=(bench["dep"], y_val), 
                    xytext=(x_offset, 10), textcoords='offset points', 
                    ha=align, va='bottom', fontsize=9, fontweight='bold', zorder=8)

        # --- CROSSED LINES FOR SPECIFIC BENCHMARKS ---
        if bench["name"] in ["multiply", "mm"]:
            # Horizontal line to the Y-axis
            ax.hlines(y=y_val, xmin=0, xmax=bench["dep"], color='gray', linestyle=':', linewidth=1.5, zorder=4)
            # Vertical line down to the X-axis
            ax.vlines(x=bench["dep"], ymin=ymin, ymax=y_val, color='gray', linestyle=':', linewidth=1.5, zorder=4)
            
            # Annotate value on the Y-axis (side)
            ax.annotate(f'{y_val:+.1f}%', xy=(0, y_val), 
                        xytext=(5, 5), textcoords='offset points', 
                        color='gray', fontweight='bold', fontsize=9, zorder=6)
            
            # Annotate value on the X-axis (bottom)
            ax.annotate(f'{bench["dep"]:.1f}%', xy=(bench["dep"], ymin), 
                        xytext=(5, 5), textcoords='offset points', 
                        color='gray', fontweight='bold', fontsize=9, zorder=6)

    # Formatting the plot
    f_base_mhz = f_base_hz / 1_000_000
    f_new_mhz = f_new_hz / 1_000_000
    ax.set_title(f"Impact of MUL Structural Change on Execution Time\n(Baseline: {f_base_mhz} MHz -> New: {f_new_mhz} MHz)", 
                 fontsize=14, fontweight='bold')
    ax.set_xlabel("Dependency Rate (% of executed instructions)", fontsize=12)
    ax.set_ylabel("Execution Time Change (%)", fontsize=12)
    ax.set_xlim(0, 15) # Lock x-axis to 15%
    
    # Y-axis formatter to explicitly show + or -
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:+.1f}%'))
    
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.legend(loc='upper left', fontsize=11)
    
    plt.tight_layout()
    
    # Save to file instead of showing the interactive window
    output_filename = "execution_time_change.png"
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Plot successfully saved as '{output_filename}'")

# --- RUN THE SCRIPT ---
if __name__ == "__main__":
    plot_execution_time_change(
        f_base_hz=66_600_000,     # MHz baseline
        f_new_hz=73_200_000       # MHz new design
    )
