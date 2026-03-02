# Bidisperse Granular Jamming in Silos: Simulation & Analysis Pipeline

This repository contains the computational pipeline used to simulate, process, and analyze the discharging and jamming of vibrated bidisperse granular media. The project focuses on the study of segregation, avalanche dynamics, and force networks (arches) using mixtures of disks and polygons.

The simulations are performed using **LIGGGHTS**, and the entire post-processing pipeline is built in **Python**, utilizing parallel computing to handle massive datasets.

## 📂 Repository Structure

The workflow is strictly modular. Raw simulation data (heavy `dumps` and `.xy` files) are kept out of the repository (via `.gitignore`), while the Python pipeline extracts, indexes, and plots the relevant physical metrics.

```text
jamming_bidisperso_vibrado/
├── LIGGGHTS_scripts/          # Input scripts (in.local, in.params) for the simulation engine
├── python_analysis/           # Core analysis pipeline
│   ├── indexer.py             # Generates a master CSV using MD5 hashes for physical parameters
│   ├── processor.py           # Extracts avalanches and spatial data (.npz) from raw .xy/dumps
│   ├── main_pipeline.py       # Master script that executes the full statistical analysis
│   ├── flow_analysis.py       # Calculates flow curves and avalanche size distributions
│   ├── arch_analysis.py       # NetworkX-based arch and force network detection
│   ├── density_map.py         # Generates heatmaps for spatial distribution
│   ├── plot_profiles.py       # Velocity and kinematic profiles along the silo
│   ├── wall_chi_variation.py  # Calculates segregation parameter ($\chi$) near the walls
│   ├── plot_wall_chi.py       # Plots the loss of $\chi$ against the injected $\chi$
│   └── temporal_chi.py        # Dynamics of the segregation parameter during discharge
├── output_results/            # Auto-generated folders by the pipeline
│   ├── 1_avalanche_data/      
│   ├── 2_spatial_maps/        
│   ├── 3_tail_distributions/  
│   ├── 4_velocity_profiles/   
│   └── 5_segregation_analysis/
└── README.md
```

## 🚀 Setup & Installation

To ensure reproducibility and avoid dependency conflicts, it is highly recommended to run this pipeline within an isolated Conda environment (e.g., using `miniforge` or `miniconda`).

1. **Clone the repository:**
   ```bash
   git clone git@github.com:yourusername/jamming_bidisperso_vibrado.git
   cd jamming_bidisperso_vibrado
   ```

2. **Create and activate the environment:**
   ```bash
   conda create --name sim_env python=3.11 numpy pandas scipy matplotlib networkx
   conda activate sim_env
   ```

## ⚙️ Usage Workflow

### 1. Indexing
Before running any analysis, the pipeline must scan the raw LIGGGHTS output directories. It reads the `params.in` files, identifies the geometry of the grains (disks/polygons), and groups statistically equivalent runs (TIRADA 1, 2, 3) using MD5 hashing.
```bash
python python_analysis/indexer.py
```
*Output: `master_sim_index.csv`*

### 2. Processing Pre-computation
This step parses the heavy raw files (like `.xy` coordinates) to detect discrete avalanches (using time thresholds) and generate lightweight spatial matrices (`.npz`).
```bash
python python_analysis/processor.py
```

### 3. Full Statistical Analysis
Once indexed and pre-processed, you can trigger the complete analytical suite. This will generate all the plots (flow curves, segregation profiles, velocity heatmaps) across all available CPU cores.
```bash
python python_analysis/main_pipeline.py
```

## 🔬 Key Physical Metrics Analyzed
* **Avalanche Statistics:** Logarithmic tail distributions for jamming events.
* **Segregation Parameter ($\chi$):** Evaluation of additive concentration in the bulk vs. silo walls.
* **Force Arches:** Identification of mechanical stability structures blocking the outlet.

---
*Developed for research in granular matter physics.*