import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
import math
import csv

class FESModel:
  def __init__(self, excitation_input, external_state_vector):
    # Model constants for an average subject (75kg - 1.75m)
    self.TAct = 0.01 # Activation constant time [sec]
    self.TDeact = 0.04 # Relaxation constant time [sec]
    self.J = 0.0197 # Inertia of the foot around ankle [kg * m^2]
    self.d = 3.7 # Moment arm of TA w.r.t the ankle [cm]
    self.B = 0.82 # Viscosity parameters
    self.cF = 11.45 # COM location w.r.t the ankle [cm]
    self.mF = 1.0275 # Mass of the foot [kg]
    self.aV = 1.33 # First force-velocity parameter
    self.fv1 = 0.18 # Second force-velocity parameter
    self.fv2 = 0.023 # Third force-velocity parameter
    self.vMax = -0.9 # Maximal contraction speed (shortnening) [m/sec]
    self.FMax = 600 # Maximal isometric force [N]
    self.W = 0.56 # Shape parameter of f-fl
    self.lT = 22.3 # Constant tendon length [cm]
    self.lMT0 = 32.1 # Muscle-tendon length at rest [cm]
    self.a = [2.10, -0.08, -7.97, 0.19, -1.79] # Parameters of elastic torque T-Elastic
    self.g = 9.81
    self.u = excitation_input
    self.x_ext = external_state_vector

  # EQN 4
  def roc_excitation(self, x, excitation_at_time):
    # x1 dot = rate of chance of dynamic level of muscle activation
    # x1 = Factivation
    x1 = x[0]
    x1_dot = (excitation_at_time - x1) * ((excitation_at_time / self.TAct) - ((1 - excitation_at_time) / self.TDeact))
    return x1_dot

  # EQN 5
  def rot_velocity(self, x):
    # x2_dot = absolute rotational velocity
    x2_dot = x[2]
    return x2_dot

  # EQN 6
  def rot_acceleration(self, state_vector, x_ext_at_time):
    # Rotational Acceleration. Left is first term, right is last
    # TODO: Change paramaters to correct function names
    left = (1 / self.J) * (self.get_muscle_force(state_vector, x_ext_at_time)) * self.d
    T_grav = self.tor_gravity(state_vector)
    T_acc = self.tor_ankle(state_vector, x_ext_at_time)
    T_ela = self.get_torque_elastic(state_vector)
    right = self.B * (x_ext_at_time[3] - state_vector[2])

    x3Dot = left + T_grav + T_acc + T_ela + right

    return x3Dot

  # EQN 7
  def tor_gravity(self, state_vector):
    # Torque of foot generated by gravity
    # Output is a negative value
    x2 = state_vector[1]
    return (-self.mF * self.cF * math.cos(x2) * self.g)

  # EQN 8
  def tor_ankle(self, state_vector, x_ext_at_time):
    # Torque of foot generated by ankle movement
    x1_ext = x_ext_at_time[0]
    x2_ext = x_ext_at_time[1]
    x2 = state_vector[1]
    return (self.mF * self.cF * (x1_ext * math.sin(x2) - (x2_ext * math.cos(x2))))

  # Equation 9 from Appendix A
  def get_torque_elastic(self, x):
    """
    :param x: state vector
    :return TEla: elastic torque of the ankle
    """
    a1 = self.a[0]
    a2 = self.a[1]
    a3 = self.a[2]
    a4 = self.a[3]
    a5 = self.a[4]

    TEla = math.exp(a1 + a2 * x[1]) - math.exp(a3 + a4 * x[1]) + a5

    return TEla

  # Equation 10 from Appendix A
  def get_muscle_force(self, x, x_ext_at_time):
    """
    :param x: state vector
    :param x_ext: external state vector
    :return Fm: TA muscular force generated by simulation
    """
    Ffl = self.get_Ffl(x, x_ext_at_time)
    Ffv = self.get_Ffv(x, x_ext_at_time)
    Fm = x[0] * self.FMax * Ffl * Ffv

    return Fm

  # Equation 11 from Appendix A
  def get_Ffl(self, x, x_ext):
    """
    :param x: state vector
    :param x_ext: external state vector
    :return Ffl: relationship between force and ankle joint angle
    """

    lMT = self.lMT0 + self.d * (x_ext[2] - x[1])  # length of the muscle-tendon complex for the TA
    lCE = lMT - self.lT # length of contractile element muscle fibres
    lCE_opt = self.lMT0 - self.lT # optimal length of CE fibre for maximal force ***CHECK***

    Ffl = math.exp(- math.pow( (lCE - lCE_opt)/(self.W*lCE_opt), 2))

    return Ffl

  # Equation 12 from Appendix A
  def get_Ffv(self, x, x_ext):
    """
    :param x: state vector
    :param x_ext: external state vector
    :return Ffv: relationship between TA's CE muscle force and its contraction speed
    """
    Ffv = 0

    vCE = self.d * (x_ext[3] - x[2])

    # case 1: muscle is contracting
    if vCE < 0:
      Ffv = ( 1 - (vCE/self.vMax) ) / ( 1 + (vCE / (self.vMax * self.fv1) ) )

    # case 2: muscle is extending or is isometric
    else:
      Ffv = ( 1 - self.aV * (vCE / self.fv2) ) / ( 1 + (vCE / self.fv2) )

    return Ffv

  def get_derivative(self, t, x):
    """
    :param x: state variables [x1, x2, x3]
    :return: time derivatives of state variables [x1Dot, x2Dot, x3Dot]
    """
    # x_ext = [i[int(t * 1000)][1] for i in self.x_ext]
    x_ext_at_time = np.zeros(4)
    for i in range(len(self.x_ext)):
      x_ext_vector = x_ext[i]
      data_point_at_time = x_ext_vector[int(t)]
      x_ext_at_time[i] = data_point_at_time[1]

    excitation_at_time = self.u[int(t)]
    x1Dot = self.roc_excitation(x, excitation_at_time)
    x2Dot = self.rot_velocity(x)
    x3Dot = self.rot_acceleration(x, x_ext_at_time)

    xDotVector = [x1Dot, x2Dot, x3Dot]


    return xDotVector


def simulate(excitation_input, external_state_vectors, initial_state, simTime):
  simulationTime = [0, simTime]

  model = FESModel(excitation_input, external_state_vectors)

  sol = solve_ivp(model.get_derivative, simulationTime, initial_state, max_step=0.001)

  time = sol.t
  ret = sol.y

  return time, ret

def get_external_data(fileName):
  ret = []

  with open('InterpolatedData/' +fileName) as file:
    plots = csv.reader(file, delimiter=',')
    for row in plots:
      ret.append(np.array([float(row[0]), float(row[1])]))
  return ret

if __name__ == "__main__":
  # fileNames = ['x1_ext_data.csv_interpolated.csv', 'x2_ext_data.csv_interpolated.csv', 'x3_ext_data.csv_interpolated.csv', 'x4_ext_data.csv_interpolated.csv']

  extData1 = get_external_data('x1_ext_data.csv_interpolated.csv')
  extData2 = get_external_data('x2_ext_data.csv_interpolated.csv')
  extData3 = get_external_data('x3_ext_data.csv_interpolated.csv')
  extData4 = get_external_data('x4_ext_data.csv_interpolated.csv')

  excitation = np.genfromtxt('excitation-data-paper.csv_interpolated.csv', delimiter=',')
  # randoms=np.random.rand(360)
  #excitation = np.full(360, 0.2)

  #excitation = np.zeros(360)
  print(excitation)
  excitationInput = excitation

  x_ext = np.array([extData1, extData2, extData3, extData4])
  initialState = np.array([0.0, -15.0, 0.0])

  time, testSim = simulate(excitationInput, x_ext, initialState, 0.36)


  dynamicActivationLevel = testSim[0]
  ankleAngle = testSim[1]
  footRotationalVelocity = testSim[2]

  plt.figure()
  plt.plot(time, dynamicActivationLevel)
  plt.title("Dynamic Activation Level")
  plt.show()

  plt.figure()
  plt.plot(time, ankleAngle)
  plt.title("Ankle Angle")
  plt.show()

  plt.figure()
  plt.plot(time, footRotationalVelocity)
  plt.title("Foot Rotational Velocity")
  plt.show()






