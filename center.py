import simpy
import random
import statistics

# --- Parameters ---
NUM_LINACS = 4
PATIENTS_PER_HOUR_PER_LINAC = 4
TREATMENT_TIME_MINUTES = 60 / PATIENTS_PER_HOUR_PER_LINAC  # 15 minutes per patient
SIMULATION_TIME_HOURS = 10
BREAKDOWN_START_HOUR = 5
BREAKDOWN_DURATION_HOURS = 2

# To test the extended day scenario, uncomment these lines
# EXTENDED_DAY = True
# EXTENDED_SIMULATION_TIME_HOURS = 12

# --- Simulation Class ---
class RadiotherapyCenter:
    def __init__(self, env):
        self.env = env
        self.linacs = simpy.Resource(env, capacity=NUM_LINACS)
        self.patients_treated = 0
        self.patient_wait_times = []
        self.wait_list_size = []

# --- Patient Process ---
def patient_arrival(env, center):
    """Generates patients at a steady rate and starts their treatment process."""
    while True:
        # Each linac can treat 4 patients per hour, so 4 linacs can treat 16 patients per hour.
        # This translates to an arrival every 60/16 = 3.75 minutes.
        yield env.timeout(random.expovariate(16 / 60))  # Exponential distribution for realistic arrivals
        
        env.process(patient_treatment(env, f"Patient_{env.now:.2f}", center))

def patient_treatment(env, name, center):
    """The patient process: waits for a linac, gets treated, and leaves."""
    arrival_time = env.now
    
    # Track waiting list size at time of arrival
    center.wait_list_size.append(len(center.linacs.queue))
    
    with center.linacs.request() as request:
        yield request
        
        wait_time = env.now - arrival_time
        center.patient_wait_times.append(wait_time)
        
        yield env.timeout(TREATMENT_TIME_MINUTES)
        
        center.patients_treated += 1

# --- Breakdown Process ---
def linac_breakdown(env, center):
    """Simulates a linac going down for a specific duration."""
    # Wait until the breakdown time
    yield env.timeout(BREAKDOWN_START_HOUR * 60)
    
    print(f"\n--- A linac is down! Time: {env.now:.2f} min ---")
    
    # Temporarily decrease the number of available linacs
    center.linacs.capacity = NUM_LINACS - 1
    yield env.timeout(BREAKDOWN_DURATION_HOURS * 60)
    
    # Linac is repaired, restore capacity
    center.linacs.capacity = NUM_LINACS
    print(f"--- Linac is repaired. Time: {env.now:.2f} min ---\n")

# --- Main Simulation Function ---
def run_simulation(simulation_time_hours):
    """Main function to set up and run the simulation."""
    env = simpy.Environment()
    center = RadiotherapyCenter(env)

    # Start the processes
    env.process(patient_arrival(env, center))
    env.process(linac_breakdown(env, center))

    # Run the simulation
    env.run(until=simulation_time_hours * 60)

    return center

# --- Reporting Results ---
def print_results(center, simulation_time):
    """Prints the key metrics of the simulation."""
    print(f"\n--- Simulation Results ({simulation_time} hours) ---")
    print(f"Total patients treated: {center.patients_treated}")
    
    if center.patient_wait_times:
        avg_wait_time = statistics.mean(center.patient_wait_times)
        max_wait_time = max(center.patient_wait_times)
        
        print(f"Average patient waiting time: {avg_wait_time:.2f} minutes")
        print(f"Maximum patient waiting time: {max_wait_time:.2f} minutes")
    else:
        print("No patients were treated in this simulation.")
        
    if center.wait_list_size:
        max_queue_size = max(center.wait_list_size)
        print(f"Maximum waiting list size (queue length): {max_queue_size}")
    else:
        print("No waiting list formed.")

# --- Running the Scenarios ---
if __name__ == '__main__':
    # Scenario 1: The normal 10-hour day with breakdown
    print("\n--- Running Normal 10-Hour Day Simulation ---")
    center_normal = run_simulation(SIMULATION_TIME_HOURS)
    print_results(center_normal, SIMULATION_TIME_HOURS)
    
    # Scenario 2: The extended 12-hour day with breakdown
    print("\n" + "="*50)
    print("\n--- Running Extended 12-Hour Day Simulation to Clear Backlog ---")
    # For this scenario, we set a longer simulation time
    # You would typically change the SIMULATION_TIME_HOURS variable at the top
    # of the script to do this. For demonstration, we'll pass it directly here.
    center_extended = run_simulation(12)
    print_results(center_extended, 12)