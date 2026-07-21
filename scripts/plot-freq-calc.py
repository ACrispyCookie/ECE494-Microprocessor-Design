import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

def plot_break_even_frequency(base_freq_mhz=66.6, base_cpi=1.0, stall_penalty=1, min_dep_rate=0, max_dep_rate=100, target_freq_mhz=None):
    """
    Plots the target frequency needed to justify removing a forwarding path
    across a customizable dependency rate range and saves the output as a PNG file.
    
    Parameters:
    base_freq_mhz (float): The initial frequency of the design in MHz.
    base_cpi (float): The baseline Cycles Per Instruction (e.g., 1.0, 1.5).
    stall_penalty (int): The number of stall cycles incurred per dependency.
    min_dep_rate (float): The starting percentage for the X-axis (default 0).
    max_dep_rate (float): The ending percentage for the X-axis (default 100).
    target_freq_mhz (float, optional): A specific frequency (MHz) to plot the break-even cutoff for.
    """
    
    # X-axis: Dependency Rate based on user-defined limits
    x_dep_rate = np.linspace(min_dep_rate, max_dep_rate, 500)
    
    # Y-axis: Required target frequency to break-even (in MHz)
    # Equation: F_new = F_base * ( (CPI_base + (Stall_Rate * Stall_Penalty)) / CPI_base )
    stall_rate = x_dep_rate / 100.0
    y_req_freq = base_freq_mhz * ((base_cpi + (stall_rate * stall_penalty)) / base_cpi)
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x_dep_rate, y_req_freq, color='#1f77b4', linewidth=2.5, 
            label="Break-even Performance Limit")
    
    # Custom Y-axis formatter to display: <Freq> MHz (+...%)
    def format_y_ticks(y, pos):
        pct_increase = ((y - base_freq_mhz) / base_freq_mhz) * 100
        if pct_increase == 0:
            return f"{y:.1f} MHz"
        return f"{y:.1f} MHz (+{pct_increase:.1f}%)"
    
    ax.yaxis.set_major_formatter(FuncFormatter(format_y_ticks))
    
    # Title and Labels
    ax.set_title(f"Break-Even Frequency vs. Dependency Rate ({min_dep_rate}% to {max_dep_rate}%)\n"
                 f"(Base: {base_freq_mhz} MHz | Base CPI: {base_cpi} | Penalty: {stall_penalty} cycles)", 
                 fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Dependency Rate (% of executed instructions)", fontsize=12)
    ax.set_ylabel("Required Target Frequency", fontsize=12)
    
    # Aesthetics
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Calculate Y limits, ensuring a plotted target point fits comfortably
    y_max = y_req_freq[-1]
    y_min = y_req_freq[0]
    
    if target_freq_mhz is not None:
        y_max = max(y_max, target_freq_mhz)
        y_min = min(y_min, target_freq_mhz)
        
    # Increased top limit slightly to give headroom for the text annotations above the dots
    top_limit = y_max * 1.10 
    bottom_limit = base_freq_mhz if min_dep_rate == 0 and y_min >= base_freq_mhz else y_min * 0.95
    
    # Fill the background zones
    ax.fill_between(x_dep_rate, y_req_freq, top_limit, 
                    color='green', alpha=0.1, label='Performance Gain Zone')
    ax.fill_between(x_dep_rate, y_req_freq, 0, 
                    color='red', alpha=0.1, label='Performance Loss Zone')
                    
    # Plot the specific custom point if provided
    if target_freq_mhz is not None:
        # Calculate the exact break-even dependency rate for this specific frequency
        break_even_dep_rate = (((target_freq_mhz / base_freq_mhz) - 1) * base_cpi / stall_penalty) * 100
        
        # Draw dashed line from the Y-axis to the curve (the cutoff point)
        ax.hlines(y=target_freq_mhz, xmin=min_dep_rate, xmax=break_even_dep_rate, color='purple', linestyle='--', linewidth=1.5, alpha=0.8, zorder=4)
        
        # Draw dashed line from the curve down to the X-axis
        ax.vlines(x=break_even_dep_rate, ymin=bottom_limit, ymax=target_freq_mhz, color='purple', linestyle='--', linewidth=1.5, alpha=0.8, zorder=4)
        
        # Plot a point on the curve for the break-even cutoff
        ax.scatter([break_even_dep_rate], [target_freq_mhz], color='purple', s=80, edgecolor='white', zorder=5, 
                   label="Max Allowed Dep Rate")
                   
        # Annotate the Y-axis intersection (Target Frequency)
        ax.annotate(f'{target_freq_mhz:.1f} MHz', xy=(min_dep_rate, target_freq_mhz), 
                    xytext=(5, 5), textcoords='offset points', color='purple', fontweight='bold', zorder=6)
        
        # Annotate the X-axis intersection (Dependency Rate)
        ax.annotate(f'{break_even_dep_rate:.1f}%', xy=(break_even_dep_rate, bottom_limit), 
                    xytext=(5, 5), textcoords='offset points', color='purple', fontweight='bold', zorder=6)

        # --- PLOTTING THE BENCHMARK DOTS ---
        # Calculate percentages dynamically based on the cycle deltas
        mm_dep_pct = ((18353 - 16625) / 16625) * 100
        multiply_dep_pct = ((2246 - 2086) / 2086) * 100

        # Define the points to plot
        benchmarks = [
            {"name": "vvadd, median,\nsort, rsort,\ndhrystone", "dep": 0.0},
            {"name": "multiply", "dep": multiply_dep_pct},
            {"name": "mm", "dep": mm_dep_pct}
        ]

        # Plot each benchmark as a dot on the 73.2 MHz line
        for bench in benchmarks:
            ax.scatter([bench["dep"]], [target_freq_mhz], color='black', s=50, edgecolor='white', zorder=7)
            
            # Align the 0% text to the left so it doesn't clip off the Y-axis bounds
            align = 'left' if bench["dep"] == 0 else 'center'
            x_offset = 5 if bench["dep"] == 0 else 0
            
            ax.annotate(bench["name"], xy=(bench["dep"], target_freq_mhz), 
                        xytext=(x_offset, 10), textcoords='offset points', 
                        ha=align, va='bottom', fontsize=9, fontweight='bold', zorder=8)
    
    # Lock the limits to the user's requested range
    ax.set_xlim(min_dep_rate, max_dep_rate)
    ax.set_ylim(bottom_limit, top_limit)
    
    ax.legend(loc="upper left")
    plt.tight_layout()
    
    # Save to file instead of showing the interactive window
    output_filename = "break_even_frequency.png"
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Plot successfully saved as '{output_filename}'")

# Run the plot: 
# Using the requested 0 to 50% range for the x-axis, and plotting the cutoff for a target frequency
if __name__ == "__main__":
    plot_break_even_frequency(
        base_freq_mhz=66.6, 
        base_cpi=1.0, 
        stall_penalty=1,
        min_dep_rate=0,
        max_dep_rate=50,
        target_freq_mhz=73.2         # Proposed new design hits 73.2 MHz
    )
