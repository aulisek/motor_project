# Motor Controller GUI for measuring mechanical properties of thin layers

This project provides a GUI application to control a motor, configure its motion parameters, and plot real-time data from a motor and an external measurement device. The GUI is built using PyQt5, and the plots are rendered with PyQtGraph.

---

## Features
1. **Motor Control**:
   - Configure velocity, position, and repetition of motor motions.
   - Start and monitor motor movements in real time.

2. **Real-Time Data Plotting**:
   - Live plotting of motor position and electrode measurements.
   - Adjustable refresh rates for plotting.

3. **Data Recording**:
   - Start and stop recording real-time data.
   - Save recorded data to a CSV file.

4. **Tabbed Interface**:
   - **Basic Options**: Configure motor parameters and start motion.
   - **Expert Options**: Advanced settings for fine-tuning motion.
   - **Data Plots**: Visualize live data and save recorded results.