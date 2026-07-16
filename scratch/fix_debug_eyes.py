import re

with open('scratch/debug_eyes.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Update custom_apply_channel signature
text = text.replace('def custom_apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc):', 
                    'def custom_apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc, out_dir, plot_spectrum_flag=False):')

# In custom_apply_channel, replace plot_eye calls
def repl_eye(m):
    # m.group(1) is the signal slice, m.group(2) is sps, m.group(3) is title
    sig = m.group(1).split('[')[0]
    sps = m.group(2)
    title = m.group(3)
    res = f'plot_eye({m.group(1)}, {sps}, {title}, output_dir=out_dir)\n    if plot_spectrum_flag:\n        plot_spectrum({sig}, baud_rate * {sps}, {title}.replace("Out", "Spectrum").replace("Eye", "Spectrum"), output_dir=out_dir)'
    return res

text = re.sub(r'plot_eye\(([^,]+),\s*([^,]+),\s*("[^"]+")\)', repl_eye, text)

# Update the call to custom_apply_channel in main
text = text.replace('tx_out, config[\'channel\'], baud_rate, sps_dac, sps_channel, sps_adc\n    )',
                    'tx_out, config[\'channel\'], baud_rate, sps_dac, sps_channel, sps_adc, out_dir, plot_spectrum_flag\n    )')

with open('scratch/debug_eyes.py', 'w', encoding='utf-8') as f:
    f.write(text)
