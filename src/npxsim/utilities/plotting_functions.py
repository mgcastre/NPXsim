# Functions to plot results from the lock model
# M. G. Castrellon | 3 April 2025

# Load Libraries
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Add function to obtain colors for chambers
def get_chamber_colors():
    """
    Returns: List with colors for UC, MC and LC (in that order).
    """
    return ['darkorange', 'green', 'royalblue']

# Define function to plot simulated water levels
def plot_water_levels(sim, lock_times, start, end, figsize=(12, 5),
                      colors=['darkorange', 'green', 'royalblue'],
                      linestyles=['-', '--', '-.', ':'], 
                      markers=['', '', '', ''],
                      return_fig=False, 
                      title='default'):
    ## Initialize plot
    fig, ax = plt.subplots(figsize=figsize)
    if title == 'default':
        ax.set_title(f'Simulated water levels in all lock chambers and basins')
    else:
        ax.set_title(title)
    
    ## Plot vertical line for when when each lockage started
    for time in lock_times:
        ax.axvline(x=time, color='black', linestyle='-', alpha=0.25)
    ## Plot water levels
    for i, cham in enumerate(['U', 'M', 'L']):
        ### Plot levels of lock chamber
        sim.loc[:, f'{cham}C'].plot(ax=ax, alpha=0.8, x_compat=True, color=colors[i], 
                                    linestyle=linestyles[0], lw=2, marker=markers[0])
        ### Plot levels of WSBs
        for j, wsb in enumerate([f'{cham}B{x}' for x in ['Top', 'Int', 'Bot']]):
            sim.loc[:, wsb].plot(ax=ax, alpha=0.7, x_compat=True, color=colors[i], 
                                 linestyle=linestyles[j+1], lw=1.7, marker=markers[j+1])

    ## Format axes
    ax.set_xlabel('Time')
    ax.set_xlim(start, end)
    ax.set_ylabel('Water Level (m)')
    date_form = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_formatter(date_form)
    ax.xaxis.set_tick_params(rotation=0, )
    for label in ax.get_xticklabels():
        label.set_horizontalalignment('center')

    ## Add legend
    ax.legend(title='Location', bbox_to_anchor=(1.0, 1.02), loc='upper left')

    ## Display plot
    plt.show()

    ## Return figure if requested
    if return_fig:
        return fig


# Define function to plot simulated and observed salinities
def plot_salinities(obs, sim, xlims, ylims, reservoirs, lock_times, figsize=(12, 5), 
                    colors=['darkorange', 'green', 'royalblue'], alpha_obs=0.5,
                    styles={'Sim': '-', 'Obs': 'o'}, 
                    return_fig=False):
    ## Initialize plot
    fig, ax = plt.subplots(figsize=figsize)
    ## Plot vertical line for when when each lockage started
    for time in lock_times:
        ax.axvline(x=time, color='black', linestyle='-', alpha=0.25)
    ## Plot salinities
    for i, cham in enumerate(['U', 'M', 'L']):
        if reservoirs == 'Chambers':
            my_res = f'{cham}C'
            handle_labels = ['UC', 'MC', 'LC']
            my_title = 'Observed and simulated salinities in lock chambers'
        elif reservoirs == 'Basins':
            my_res = f'{cham}BInt'
            handle_labels = ['UIB', 'MIB', 'LIB']
            my_title = 'Observed and simulated salinities in intermediate basins'
        else:
            raise ValueError("Reservoirs must be either 'Chambers' or 'Basins'.")
        ### Plot simulated salinities
        sim.loc[:, my_res].plot(ax=ax, alpha=0.8, x_compat=True, color=colors[i], 
                                lw=2, linestyle=styles['Sim'], marker='', label=f'{my_res} Sim')
        
        ## Plot observed salinities
        obs.loc[:, my_res].plot(ax=ax, alpha=alpha_obs, x_compat=True, color=colors[i], 
                                linestyle='', marker=styles['Obs'], markersize=6, 
                                label=f'{my_res} Obs')
    ## Add title to the plot
    ax.set_title(my_title)
    ## Format axes
    ax.set_xlabel('Time')
    ax.set_xlim(xlims[0], xlims[1])
    ax.set_ylabel('Salinity (PSU)')
    ax.set_ylim(ylims[0], ylims[1])
    date_form = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_formatter(date_form)
    ax.xaxis.set_tick_params(rotation=0, )
    for label in ax.get_xticklabels():
        label.set_horizontalalignment('center')

    ## Format and legend
    lines, _ = ax.get_legend_handles_labels()
    sim_lines = [lines[0], lines[2], lines[4]]
    obs_lines = [lines[1], lines[3], lines[5]]
    
    leg1 = ax.legend(sim_lines, handle_labels, title='Simulated', loc='upper left',
                     bbox_to_anchor=(1.0, 1.0), frameon=False)
    
    leg2 = ax.legend(obs_lines, handle_labels, title='Observed', loc='upper left',
                     bbox_to_anchor=(1.0, 0.7), frameon=False)

    fig.add_artist(leg1)
    fig.add_artist(leg2)

    ## Display plot
    plt.tight_layout(w_pad=0.5)
    plt.show()

    ## Return figure if requested
    if return_fig:
        return fig