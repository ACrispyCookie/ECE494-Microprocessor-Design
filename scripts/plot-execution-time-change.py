import matplotlib.pyplot as plt
import numpy as np

def plot_execution_time_change(f_base_hz, f_new_hz, base_cpi=1.0):
    """
    Plots the % change in execution time of the new design vs. the baseline.
    
    Parameters:
    f_base_hz (float): Baseline frequency in Hz (e.g., 50_000_000 for 50 MHz).
    f_new_hz (float): New frequency in Hz (e.g., 55_000_000 for 55 MHz).
    base_cpi (float): The baseline Cycles Per Instruction (default is 1.0).
    """
    
    # Create an array of potential MUL dependency percentages from 0% to 20%
    x_pct = np.linspace(0, 20, 200)
    
    # 1. Calculate New CPI for the entire array
    # Every 1% of MUL dependency adds 0.01 to the CPI (due to the 1-cycle stall)
    cpi_new = base_cpi + (x_pct / 100)
    
    # 2. Calculate Execution Time Ratio: (CPI_new / CPI_base) * (F_base / F_new)
    # Note: Instruction count cancels out!
    time_ratio = (cpi_new / base_cpi) * (f_base_hz / f_new_hz)
    
    # 3. Convert to Percentage Change (+ means slower, - means faster)
    exec_time_change_pct = (time_ratio - 1) * 100

    # Calculate the exact break-even point (where execution time change is 0%)
    break_even_pct = ((f_new_hz / f_base_hz) - 1) * base_cpi * 100

    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot the main trend line
    ax.plot(x_pct, exec_time_change_pct, color='black', linewidth=2, zorder=3)
    
    # Add a break-even horizontal line at 0%
    ax.axhline(0, color='gray', linestyle='--', linewidth=1.5, zorder=2)
    
    # Fill areas to show "Faster" vs "Slower"
    ax.fill_between(x_pct, exec_time_change_pct, 0, where=(exec_time_change_pct < 0), 
                    color='green', alpha=0.2, label='Faster (Execution Time Decreased)')
    ax.fill_between(x_pct, exec_time_change_pct, 0, where=(exec_time_change_pct > 0), 
                    color='red', alpha=0.2, label='Slower (Execution Time Increased)')
    
    # Draw dashed vertical line from break-even point to the x-axis
    if 0 <= break_even_pct <= x_pct[-1]:
        ymin, ymax = ax.get_ylim()
        
        # Draw the dashed line down to the bottom
        ax.vlines(x=break_even_pct, ymin=ymin, ymax=0, color='purple', linestyle='--', linewidth=1.5, zorder=4)
        
        # Plot the point on the break-even line (0%)
        ax.scatter([break_even_pct], [0], color='purple', s=80, zorder=5, label='Break-even Cutoff')
        
        # Annotate the X-axis intersection (Dependency Rate)
        ax.annotate(f'{break_even_pct:.1f}%', xy=(break_even_pct, ymin), 
                    xytext=(5, 5), textcoords='offset points', color='purple', fontweight='bold', zorder=6)
                    
        ax.set_ylim(ymin, ymax) # Lock the y-axis limits back to original bounds

    # Formatting the plot
    f_base_mhz = f_base_hz / 1_000_000
    f_new_mhz = f_new_hz / 1_000_000
    ax.set_title(f"Impact of MUL Structural Change on Execution Time\n(Baseline: {f_base_mhz} MHz -> New: {f_new_mhz} MHz)", 
                 fontsize=14, fontweight='bold')
    ax.set_xlabel("MUL Forwarding Path Usage (% of instructions)", fontsize=12)
    ax.set_ylabel("Execution Time Change (%)", fontsize=12)
    
    # Y-axis formatter to explicitly show + or -
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:+.1f}%'))
    
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.legend(loc='upper left', fontsize=11)
    
    plt.tight_layout()
    plt.show()

# --- RUN THE SCRIPT ---
# Example Scenario: 
# The baseline core ran at 66.6 MHz, and removing the forwarding path 
# allowed you to hit 73.0 MHz.
if __name__ == "__main__":
    plot_execution_time_change(
        f_base_hz=66_600_000,     # MHz baseline
        f_new_hz=73_000_000       # MHz new design
    )