# Workspace Rules for eLPO_antigravity

These rules apply specifically to this IMDD 112G/224G PAM4 LPO simulation project.

## Development Philosophy
- **DSP Chip Prototype, Not Software Engineering**: Treat this project as a bare-metal DSP chip algorithm prototype. Avoid overly complex Object-Oriented (OO) patterns, abstract classes, or deep inheritance hierarchies. Keep the data flow straightforward and procedural where possible.
- **Pure White-Box Implementations**: All signal processing and optimization algorithms MUST be implemented purely from scratch using `numpy`. 
  - Do NOT use opaque third-party toolboxes for MLSE, filtering, or optimization (e.g., no `scikit-learn`, `hyperopt`, etc.).
  - Ensure the internal mathematics (like Bayesian Optimization Gaussian Processes or Viterbi trellis decoding) are fully visible, transparent, and mathematically accurate.

## Architecture and Data Flow
- **Multi-Rate System**: 
  - The DSP blocks (Tx/Rx) must operate at 2 Samples Per Symbol (sps).
  - The Analog Channel (Tx Analog, Fiber, Rx Analog) must operate at 8 sps.
  - Implement Zero-Order Hold (ZOH) upsampling before the analog channel, and downsampling before the Rx DSP.
- **Configuration**: Always manage parameters through `config.xlsx`. Do not hardcode parameters in the script files. If new parameters are needed, add them to `create_config.py` first.

## Language and Documentation
- **Communication Language**: Always communicate with the User in Chinese unless specified otherwise.
- **Documentation**: Write inline code comments, git commit messages, and Markdown documentation (like `README.md` or reports) in English.
- **Document Asset Tracking**: Keep track of standard-compliant parameters (like CEI-112G PCB loss or bandwidth values) and simulation run outputs in the `docs/` directory to prevent context loss. Clean up obsolete graphs (e.g. `*.png`) when new architectural changes invalidate them.
