# Radiotherapy Center Simulator

This project is a discrete-event simulation of a radiotherapy treatment center's patient workflow, built using Python, `simpy`, and `tkinter`. It provides a graphical user interface (GUI) to configure various operational parameters and visualizes the impact on patient backlog, treatment capacity, and wait times.



## Features

- **Configurable Resources:** Set the number of LINACs, treatment hours per day, and patient throughput per hour.
- **Dynamic Patient Intake:** Control the number of new patients arriving each week.
- **Adjustable Case Mix:** Use interactive sliders to define the percentage mix of patients requiring treatment durations from 1 to 6 weeks. The percentages automatically adjust to always sum to 100%.
- **Stochastic Events:**
  - **Machine Breakdowns:** Models random, weekly breakdowns for each LINAC, interrupting a number of patients based on the breakdown duration.
  - **Scheduled Downtime:** Simulates a recurring, center-wide closure day (e.g., for maintenance or training) every 4 weeks, which interrupts all active treatments.
  - **Dynamic Overtime:** Automatically activates overtime (2 extra hours/day) on LINACs one-by-one when the patient backlog exceeds a set threshold, and scales down when the backlog decreases.
- **Detailed Metrics & Visualization:**
  - A real-time plot shows the number of patients in the backlog, patients actively on treatment, and patients being treated in overtime slots.
  - A summary report provides key performance indicators like total patients treated, backlog sizes, patient wait times, and detailed overtime statistics.

## Requirements

This program requires Python 3 and the following libraries:

- `simpy`: For the core discrete-event simulation framework.
- `matplotlib`: For plotting the results.

`tkinter` is also used and is typically included in standard Python installations.

You can install the required libraries using pip:
```bash
pip install simpy matplotlib
```

## How to Run

1.  Ensure you have Python and the required libraries installed.
2.  Save the code as a Python file (e.g., `center.py`).
3.  Run the script from your terminal:
    ```bash
    python center.py
    ```

## How to Use the Simulator

The application window is divided into several sections:

1.  **Simulation Parameters:**
    - **Number of LINACs:** The total number of treatment machines available.
    - **Patients per Hour per LINAC:** The treatment rate for a single machine.
    - **Simulation Time (Weeks):** The total duration the simulation will run.
    - **Weekly New Patients:** The number of new patients that enter the system each week.
    - **Breakdown Duration (hours):** The length of a single random machine breakdown. This determines how many patient slots are missed.
    - **Treatment Day Hours:** The number of hours per day the center is operational.

2.  **Treatment Duration Mix (%):**
    - Use the sliders to adjust the relative proportion of patients with different treatment lengths (1 to 6 weeks).
    - The percentage labels to the right of the sliders update in real-time, always ensuring the total mix is 100%.

3.  **Controls:**
    - Click the **"Run Simulation"** button to start the simulation with the current parameters. The button will be disabled while the simulation is running.

4.  **Outputs:**
    - **Summary:** After a run, this text box displays the key performance indicators.
    - **Patient Status Over Time:** This graph visualizes the number of patients waiting in the backlog and the number of patients actively receiving treatment over the course of the simulation.

## Simulation Model Details

- **Time Unit:** The base unit of time in the simulation is one **working day**. A week consists of 5 working days.
- **Patient Flow:**
  1.  New patients are generated weekly by the `patient_intake` process and placed in a `backlog` queue.
  2.  The `treatment_scheduler` process pulls patients from the `backlog` as soon as a `treatment_slot` becomes available.
  3.  The `patient_treatment_process` simulates the multi-day duration of a patient's treatment course.
- **Interruptions:** Both random breakdowns and scheduled closure days are handled using `simpy.Interrupt`. When a patient's treatment process is interrupted:
  - The time already spent on the current day's treatment is recorded.
  - The remaining treatment duration is recalculated.
  - A one-day penalty is added to account for the missed session, extending their overall treatment time.
- **Overtime Logic:**
  - An `overtime_manager` process checks the backlog size daily.
  - If the backlog exceeds 10 patients, it adds one LINAC's worth of capacity (2 hours of treatment slots) to the system. This can repeat on subsequent days until all LINACs are in overtime.
  - If the backlog drops to 10 or below, it removes overtime capacity one LINAC at a time.