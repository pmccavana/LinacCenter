import simpy
import random
import statistics
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading

# --- Parameters ---
# Default values for the new simulation model
NUM_LINACS = 4
PATIENTS_PER_HOUR_PER_LINAC = 4
SIMULATION_TIME_WEEKS = 26 # 6 months
WEEKLY_NEW_PATIENTS = 20
BREAKDOWN_DURATION_HOURS = 2
TREATMENT_DAY_HOURS = 10

# --- Simulation Class ---
class RadiotherapyCenter:
    def __init__(self, env, num_linacs, patients_per_hour_linac, treatment_day_hours):
        self.env = env
        # Capacity is the total number of patients that can be in treatment concurrently
        daily_sessions_per_linac = treatment_day_hours * patients_per_hour_linac
        total_capacity = num_linacs * daily_sessions_per_linac
        self.treatment_slots = simpy.Container(env, capacity=total_capacity, init=total_capacity)
        # A store for incoming patients waiting to start their treatment course
        self.backlog = simpy.Store(env)
        # Data for plotting backlog size over time
        self.backlog_data = []
        self.on_treatment_data = []
        self.patients_started = 0
        self.on_treatment_count = 0
        self.next_patient_id = 0
        self.active_treatments = {} # Maps patient_id -> process

# --- Patient Process ---
def patient_intake(env, center, weekly_new_patients):
    """Generates new patients weekly, scheduling them immediately if capacity
    exists, or adding the remainder to the backlog."""
    # Each patient has an equal chance of being assigned a 1, 2, 3, 4, or 5-week treatment.
    treatment_options_weeks = [1, 2, 3, 4, 5]

    while True:
        new_patient_durations_weeks = random.choices(treatment_options_weeks, k=weekly_new_patients)
        patients_to_process = [{'duration_days': d * 5} for d in new_patient_durations_weeks]

        # Phase 1: Fill any immediately available slots, bypassing the backlog.
        # This loop continues as long as there are free slots and patients to schedule.
        while center.treatment_slots.level > 0 and len(patients_to_process) > 0:
            patient = patients_to_process.pop(0)
            # Since we checked the level, this get() is non-blocking but must be yielded.
            yield center.treatment_slots.get(1)
            patient_id = center.next_patient_id
            center.next_patient_id += 1
            env.process(patient_treatment_process(env, center, patient, patient_id))

        # Phase 2: If any patients remain, all slots are full. Add them to the backlog.
        for patient in patients_to_process:
            yield center.backlog.put(patient)

        # Wait 5 working days for the next weekly intake
        yield env.timeout(5)

def treatment_scheduler(env, center):
    """Pulls patients from the backlog as treatment slots become free."""
    while True:
        # 1. Wait for a patient to appear in the backlog. This is the trigger.
        patient = yield center.backlog.get()

        # 2. Now that we have a backlogged patient, wait for a treatment slot to free up.
        yield center.treatment_slots.get(1)

        # 3. Start the patient's treatment in a new process.
        #    This process is now responsible for releasing the slot.
        patient_id = center.next_patient_id
        center.next_patient_id += 1
        env.process(patient_treatment_process(env, center, patient, patient_id))

def patient_treatment_process(env, center, patient, patient_id):
    """Represents the actual treatment course for a single patient, which can be interrupted."""
    center.patients_started += 1
    center.on_treatment_count += 1
    center.active_treatments[patient_id] = env.active_process

    remaining_duration = patient['duration_days']
    while remaining_duration > 0:
        try:
            # Store start time of this treatment segment
            start_time = env.now
            yield env.timeout(remaining_duration)
            # If we get here, treatment finished without interruption
            remaining_duration = 0
        except simpy.Interrupt:
            # Interrupted by a breakdown!
            time_passed = env.now - start_time
            remaining_duration -= time_passed
            # Add one day penalty for the missed treatment
            remaining_duration += 1

    # Treatment is done, clean up.
    del center.active_treatments[patient_id]
    yield center.treatment_slots.put(1)
    center.on_treatment_count -= 1

# --- Breakdown Process ---
def linac_breakdown_process(env, center, breakdown_impact):
    """A process for a single LINAC, causing one random breakdown per week."""
    while True:
        # Wait for a random time within the 5-day working week.
        random_delay_in_week = random.uniform(0, 5)
        yield env.timeout(random_delay_in_week)

        # Trigger the breakdown: interrupt a number of patients
        num_active_patients = len(center.active_treatments)
        if num_active_patients > 0:
            # A single linac breakdown impacts a number of patients equal to its lost session capacity.
            num_to_interrupt = min(breakdown_impact, num_active_patients)
            patients_to_interrupt_ids = random.sample(list(center.active_treatments.keys()), k=num_to_interrupt)
            for pid in patients_to_interrupt_ids:
                # Check if patient still exists, as they might have finished treatment
                # between sampling and interruption.
                if pid in center.active_treatments:
                    center.active_treatments[pid].interrupt()

        # Wait for the rest of the week to pass before the next cycle.
        yield env.timeout(5 - random_delay_in_week)

# --- Monitoring Process ---
def monitor(env, center):
    """Records key metrics every day for plotting."""
    while True:
        center.backlog_data.append((env.now, len(center.backlog.items)))

        # Calculate patients currently on treatment (capacity - available slots)
        center.on_treatment_data.append((env.now, center.on_treatment_count))

        yield env.timeout(1) # Record daily

# --- Main Simulation Function ---
def run_simulation(params):
    """Main function to set up and run the simulation."""
    env = simpy.Environment()

    # Unpack parameters from the GUI
    num_linacs = int(params['num_linacs'])
    p_per_hr = int(params['patients_per_hour_linac'])
    weekly_new = int(params['weekly_new_patients'])
    breakdown_hrs = int(params['breakdown_duration_hr'])
    treatment_day_hrs = int(params['treatment_day_hours'])
    sim_weeks = int(params['sim_time_weeks'])

    center = RadiotherapyCenter(env, num_linacs, p_per_hr, treatment_day_hrs)

    # The breakdown's impact is the number of treatment sessions lost
    breakdown_impact = 1 * breakdown_hrs * p_per_hr

    # Start the processes
    env.process(monitor(env, center)) # Start monitoring first to get t=0 state
    env.process(patient_intake(env, center, weekly_new))
    # Start one scheduler process. It will handle all slot assignments.
    env.process(treatment_scheduler(env, center))
    # Start an independent, random breakdown process for each LINAC
    for _ in range(num_linacs):
        env.process(linac_breakdown_process(env, center, breakdown_impact))

    # Run the simulation
    sim_duration_days = sim_weeks * 5 # 5 working days per week
    env.run(until=sim_duration_days)

    return center

# --- Reporting Results ---
def format_results(center, sim_time_weeks):
    """Formats the key metrics of the simulation into a string."""
    results = []
    results.append(f"--- Simulation Results ({sim_time_weeks} Weeks) ---")
    results.append(f"Total patients who started treatment: {center.patients_started}")
    final_backlog = len(center.backlog.items)
    results.append(f"Patients still in backlog at end: {final_backlog}")

    if center.backlog_data:
        max_backlog = max(size for time, size in center.backlog_data)
        results.append(f"Maximum backlog size reached: {max_backlog}")

    return "\n".join(results)

# --- GUI Application ---
class SimulationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Radiotherapy Center Simulator")
        self.geometry("800x750")

        self.params = {}
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Input Parameters Frame ---
        params_frame = ttk.LabelFrame(main_frame, text="Simulation Parameters", padding="10")
        params_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        params_frame.columnconfigure(1, weight=1)

        param_defs = {
            'num_linacs': ("Number of LINACs:", NUM_LINACS),
            'patients_per_hour_linac': ("Patients per Hour per LINAC:", PATIENTS_PER_HOUR_PER_LINAC),
            'sim_time_weeks': ("Simulation Time (Weeks):", SIMULATION_TIME_WEEKS),
            'weekly_new_patients': ("Weekly New Patients:", WEEKLY_NEW_PATIENTS),
            'breakdown_duration_hr': ("Breakdown Duration (hours):", BREAKDOWN_DURATION_HOURS),
            'treatment_day_hours': ("Treatment Day Hours:", TREATMENT_DAY_HOURS)
        }

        for i, (key, (label, default)) in enumerate(param_defs.items()):
            ttk.Label(params_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(params_frame, width=10)
            entry.grid(row=i, column=1, sticky=tk.W, pady=2)
            entry.insert(0, str(default))
            self.params[key] = entry

        # --- Controls ---
        self.run_button = ttk.Button(main_frame, text="Run Simulation", command=self.start_simulation_thread)
        self.run_button.grid(row=2, column=0, pady=10, sticky=tk.W)

        # --- Results Frame ---
        results_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        results_frame.columnconfigure(0, weight=1)

        self.results_text = tk.Text(results_frame, wrap=tk.WORD, height=5)
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # --- Plot Frame ---
        plot_frame = ttk.LabelFrame(main_frame, text="Patient Status Over Time", padding="10")
        plot_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.rowconfigure(3, weight=1)
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def start_simulation_thread(self):
        self.run_button.config(state="disabled")
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, "Running simulation...")
        self.ax.clear()
        self.ax.set_xlabel("Time (Working Days)")
        self.ax.set_ylabel("Number of Patients")
        self.ax.grid(True)
        self.ax.set_title("Patient Status Over Time")
        self.canvas.draw()

        try:
            # Convert GUI inputs to numbers
            current_params = {key: entry.get() for key, entry in self.params.items()}
        except ValueError:
            self.results_text.delete("1.0", tk.END)
            self.results_text.insert(tk.END, "Error: All parameters must be valid numbers.")
            self.run_button.config(state="normal")
            return

        # Run simulation in a separate thread to not freeze the GUI
        thread = threading.Thread(target=self.run_and_display_results, args=(current_params,))
        thread.start()

    def run_and_display_results(self, params):
        center = run_simulation(params)
        results_str = format_results(center, int(params['sim_time_weeks']))

        # Schedule the GUI update to run in the main thread
        self.after(0, self.update_gui, results_str, center.backlog_data, center.on_treatment_data)

    def update_gui(self, results_str, backlog_data, on_treatment_data):
        # Update the text results
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, results_str)

        # Update the plot
        self.ax.clear()

        if backlog_data:
            days, backlog_sizes = zip(*backlog_data)
            self.ax.plot(days, backlog_sizes, label='Patients in Backlog', marker='.', linestyle='-', markersize=4)

        if on_treatment_data:
            days, on_treatment_sizes = zip(*on_treatment_data)
            self.ax.plot(days, on_treatment_sizes, label='Patients on Treatment', marker='.', linestyle='-', markersize=4)

        self.ax.set_xlabel("Time (Working Days)")
        self.ax.set_ylabel("Number of Patients")
        self.ax.set_title("Patient Status Over Time")
        self.ax.grid(True)
        self.ax.legend()
        self.canvas.draw()

        self.run_button.config(state="normal")

if __name__ == '__main__':
    app = SimulationApp()
    app.mainloop()