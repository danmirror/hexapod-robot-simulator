from copy import deepcopy
from hexapod.const import HEXAPOD_POSE
import numpy as np
from hexapod.models import VirtualHexapod, Linkage
from hexapod.points import (
  Point,
  cross,
  dot,
  length,
  scale,
  subtract_vectors,
  add_vectors,
  scalar_multiply,
  vector_from_to,
  get_unit_vector,
  frame_to_align_vector_a_to_b,
  is_triangle,
  project_vector_onto_plane,
  angle_between,
  angle_opposite_of_last_side,
  rotz
)

def is_counter_clockwise(a, b, n):
  return dot(a, cross(b, n)) > 0


def inverse_kinematics_update(
  hexapod,
  rot_x,
  rot_y,
  rot_z,
  end_x,
  end_y,
  end_z,
):
  x_axis = Point(1, 0, 0)
  tx = end_x * hexapod.mid
  ty = end_y * hexapod.side
  tz = end_z * hexapod.tibia

  hexapod.detach_body_rotate_and_translate(rot_x, rot_y, rot_z, tx, ty, tz)
  starting_hexapod = deepcopy(hexapod)

  body_normal = hexapod.z_axis
  for i in range(hexapod.LEG_COUNT):
    body_contact = hexapod.body.vertices[i]
    foot_tip = hexapod.legs[i].foot_tip()
    if body_contact.z < foot_tip.z:
      return starting_hexapod, None, 'Impossible twist at given height: body contact shoved on ground'

  poses = deepcopy(HEXAPOD_POSE)

  for i in range(hexapod.LEG_COUNT):
    leg_name = hexapod.legs[i].name
    body_contact = hexapod.body.vertices[i]
    foot_tip = hexapod.legs[i].foot_tip()
    body_to_foot_vector = vector_from_to(body_contact, foot_tip)
    unit_coxia_vector = project_vector_onto_plane(body_to_foot_vector, body_normal)
    coxia_vector = scalar_multiply(unit_coxia_vector, hexapod.coxia)
    coxia_point = add_vectors(body_contact, coxia_vector)

    if coxia_point.z < foot_tip.z:
      return starting_hexapod, None, 'Impossible twist at given height: coxia joint shoved on ground'

    p0 = Point(0, 0, 0)
    p1 = Point(hexapod.coxia, 0, 0)
    dd = angle_between(unit_coxia_vector, body_to_foot_vector)
    e = length(body_to_foot_vector)
    p3 = Point(e * np.cos(np.radians(dd)), 0, -e * np.sin(np.radians(dd)))
    coxia_to_foot_vector2d = vector_from_to(p1, p3)
    d = length(vector_from_to(p1, p3))
    a = hexapod.tibia
    b = hexapod.femur
    aa = angle_opposite_of_last_side(d, b, a)
    ee = angle_between(coxia_to_foot_vector2d, x_axis)

    if is_triangle(a, b, d):

      if p3.z > 0:
        beta = aa + ee
      else:
        beta = aa - ee

      height = -p3.z
      x_ = b * np.cos(np.radians(beta))
      z_ = b * np.sin(np.radians(beta))
      x_ = p1.x + x_
      if height > a:
        z_ =  -z_
      if beta < 0:
        if z_ > 0:
          z_ = -z_
      p2 = Point(x_, 0, z_)

      if p2.z < p3.z:
        return starting_hexapod, None, f'{leg_name} leg cant go through ground.'
    else:
      if a + b < d:
        femur_tibia_direction = get_unit_vector(coxia_to_foot_vector2d)
        femur_vector = scalar_multiply(femur_tibia_direction, a)
        p2 = add_vectors(p1, femur_vector)
        tibia_vector = scalar_multiply(femur_tibia_direction, b)
        p3 = add_vectors(p2, tibia_vector)
      elif d + b < a:
        return starting_hexapod, None, f"Can't reach foot tip. {leg_name} leg's Tibia length is too long."
      else:
        return starting_hexapod, None, f"Can't reach foot tip. {leg_name} leg's Femur is too long."

    #print(f'p0: {p0}')
    #print(f'p1: {p1}')
    #print(f'p2: {p2}')
    #print(f'p3: {p3}')

    twist = angle_between(unit_coxia_vector, hexapod.x_axis)
    is_ccw = is_counter_clockwise(unit_coxia_vector, hexapod.x_axis, hexapod.z_axis)
    if is_ccw:
      twist_frame = rotz(-twist)
    else:
      twist_frame = rotz(twist)

    points = [p0, p1, p2, p3]
    for point in points:
      point.update_point_wrt(twist_frame)
      assert hexapod.body_rotation_frame is not None
      point.update_point_wrt(hexapod.body_rotation_frame)
      point.move_xyz(body_contact.x, body_contact.y, body_contact.z)

    # Sanity Check
    coxia = length(vector_from_to(p0, p1))
    femur = length(vector_from_to(p1, p2))
    tibia = length(vector_from_to(p2, p3))

    assert np.isclose(hexapod.coxia, coxia, atol=1), f'wrong coxia vector length. {leg_name} coxia:{coxia}'
    assert np.isclose(hexapod.femur, femur, atol=1), f'wrong femur vector length. {leg_name} femur:{femur}'
    assert np.isclose(hexapod.tibia, tibia, atol=1), f'wrong tibia vector length. {leg_name} tibia:{tibia}'

    hexapod.legs[i].p0 = p0
    hexapod.legs[i].p1 = p1
    hexapod.legs[i].p2 = p2
    hexapod.legs[i].p3 = p3

  #print(f'poses: {poses}')
  return hexapod, poses, None
