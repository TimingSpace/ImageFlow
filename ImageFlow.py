
from __future__ import print_function

import copy
import cv2
import json
import matplotlib.pyplot as plt
import numpy as np
import numpy.linalg as LA

from ColorMapping import color_map

# Global variables used as constants.

# DATA_DIR      = "./data/test/blockworld_move_x_planner"
# # x planner.
# POSE_ID_0     = "000000_532136"
# POSE_ID_1     = "000019_538142"

# # y planner.
# DATA_DIR      = "./data/test/blockworld_move_y_planner"
# POSE_ID_0     = "000000_566604"
# POSE_ID_1     = "000021_573897"

# yaw planner.
DATA_DIR      = "./data/test/blockworld_move_yaw_planner"
POSE_ID_0     = "000000_490248"
POSE_ID_1     = "000013_496146"

POSE_FILENAME = DATA_DIR + "/pose_name.json"
POSE_DATA     = DATA_DIR + "/pose_wo_name.npy"
OUT_DIR       = DATA_DIR + "/ImageFlow"
POSE_NAME     = "pose_name"

DEPTH_DIR     = DATA_DIR + "/depth_plan"
DEPTH_SUFFIX  = "_depth"
DEPTH_EXT     = ".npy"

CAM_FOCAL     = 320
IMAGE_SIZE    = (360, 640)

DISTANCE_RANGE = 50

ply_header = '''ply
format ascii 1.0
element vertex %(vert_num)d
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
'''

PLY_COLORS = [\
    "#2980b9",\
    "#27ae60",\
    "#f39c12",\
    "#c0392b",\
    ]

PLY_COLOR_LEVELS = 20

def write_ply(fn, verts, colors):
    verts  = verts.reshape(-1, 3)
    colors = colors.reshape(-1, 3)
    verts  = np.hstack([verts, colors])

    with open(fn, 'wb') as f:
        f.write((ply_header % dict(vert_num=len(verts))).encode('utf-8'))
        np.savetxt(f, verts, fmt='%f %f %f %d %d %d ')

def depth_to_color(depth, limit = None):

    d  = copy.deepcopy(depth)
    if ( limit is not None ):
        d[ d>limit ] = limit

    color = np.zeros((depth.shape[0], depth.shape[1], 3), dtype = float)
    color[:, :, 0] = d
    color[:, :, 1] = d
    color[:, :, 2] = d

    color = ( color - d.min() ) / ( d.max() - d.min() ) * 255
    color = color.astype(np.uint8)

    return color

def output_to_ply(fn, X, imageSize, rLimit):
    vertices = np.zeros(( imageSize[0], imageSize[1], 3 ), dtype = np.float)
    vertices[:, :, 0] = X[0, :].reshape(imageSize)
    vertices[:, :, 1] = X[1, :].reshape(imageSize)
    vertices[:, :, 2] = X[2, :].reshape(imageSize)
    
    vertices = vertices.reshape((-1, 3))

    r = LA.norm(vertices, axis=1).reshape((-1,1))
    mask = r < rLimit
    mask = mask.reshape(( mask.size ))

    r = r[ mask ]

    cr, cg, cb = color_map(r, PLY_COLORS, PLY_COLOR_LEVELS)

    colors = np.zeros( (r.size, 3), dtype = np.uint8 )

    # import ipdb; ipdb.set_trace()

    colors[:, 0] = cr.reshape( cr.size )
    colors[:, 1] = cg.reshape( cr.size )
    colors[:, 2] = cb.reshape( cr.size )

    write_ply(fn, vertices[mask, :], colors)

def load_IDs(fn):
    fp = open(fn, "r")

    if ( fp is None ):
        print("Could not open %s" % (fn))
        return -1
    
    lines = fp.readlines()

    fp.close()

    IDs = []

    for l in lines:
        IDs.append( l[:-2] )

    return 0, IDs

def load_IDs_JSON(fn, poseName = None):
    fp = open(fn, "r")

    if ( fp is None ):
        print("Could not open %s" % (fn))
        return -1
    
    dict = json.load(fp)

    fp.close()

    if ( poseName is None ):
        return 0, dict["ID"]
    else:
        return 0, dict[poseName]

def from_quaternion_to_rotation_matrix(q):
    """
    q: A numpy vector, 4x1.
    """

    qi2 = q[0, 0]**2
    qj2 = q[1, 0]**2
    qk2 = q[2, 0]**2

    qij = q[0, 0] * q[1, 0]
    qjk = q[1, 0] * q[2, 0]
    qki = q[2, 0] * q[0, 0]

    qri = q[3, 0] * q[0, 0]
    qrj = q[3, 0] * q[1, 0]
    qrk = q[3, 0] * q[2, 0]

    s = 1.0 / ( q[3, 0]**2 + qi2 + qj2 + qk2 )
    ss = 2 * s

    R = [\
        [ 1.0 - ss * (qj2 + qk2), ss * (qij - qrk), ss * (qki + qrj) ],\
        [ ss * (qij + qrk), 1.0 - ss * (qi2 + qk2), ss * (qjk - qri) ],\
        [ ss * (qki - qrj), ss * (qjk + qri), 1.0 - ss * (qi2 + qj2) ],\
    ]

    R = np.array(R, dtype = np.float)

    return R

def get_pose_by_ID(ID, poseIDs, poseData):
    idxPose = poseIDs.index( ID )
    data    = poseData[idxPose, :].reshape((-1, 1))
    t = data[:3, 0].reshape((-1, 1))
    q = data[3:, 0].reshape((-1, 1))
    R = from_quaternion_to_rotation_matrix(q)

    return LA.inv(R), -t, q

def du_dv(nu, nv, imageSize):
    wIdx = np.linspace( 0, imageSize[1] - 1, imageSize[1] )
    hIdx = np.linspace( 0, imageSize[0] - 1, imageSize[0] )

    u, v = np.meshgrid(wIdx, hIdx)

    return nu - u, nv - v

def show(ang, mag, shape):
    """ang: degree"""
    # Use Hue, Saturation, Value colour model 
    hsv = np.zeros(shape, dtype=np.uint8)
    hsv[..., 1] = 255

    # mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1]

    hsv[..., 0] = (ang + 180)/ 2
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    np.savetxt(DATA_DIR + "/rgb.dat", rgb[:, :, 0], fmt="%3d")

    plt.imshow(rgb)
    plt.show()

class CameraBase(object):
    def __init__(self, focal, imageSize):
        self.focal = focal
        self.imageSize = copy.deepcopy(imageSize) # List or tuple, (height, width)
        self.size = self.imageSize[0] * self.imageSize[1]

        self.pu = self.imageSize[1] / 2
        self.pv = self.imageSize[0] / 2

        self.cameraMatrix = np.eye(3, dtype = np.float)
        self.cameraMatrix[0, 0] = self.focal
        self.cameraMatrix[1, 1] = self.focal
        self.cameraMatrix[0, 2] = self.pu
        self.cameraMatrix[1, 2] = self.pv

        self.worldR = np.zeros((3,3), dtype = np.float)
        self.worldR[0, 1] = 1.0
        self.worldR[1, 2] = 1.0
        self.worldR[2, 0] = 1.0

        self.worldRI = np.zeros((3,3), dtype = np.float)
        self.worldRI[0, 2] = 1.0
        self.worldRI[1, 0] = 1.0
        self.worldRI[2, 1] = 1.0

    def from_camera_frame_to_image(self, coor):
        """
        coor: A numpy column vector, 3x1.
        return: A numpy column vector, 2x1.
        """
        
        coor = self.worldR.dot(coor)
        x = self.cameraMatrix.dot(coor)
        x = x / x[2,:]

        return x[0:2, :]

    def from_depth_to_x_y(self, depth):
        wIdx = np.linspace( 0, self.imageSize[1] - 1, self.imageSize[1] )
        hIdx = np.linspace( 0, self.imageSize[0] - 1, self.imageSize[0] )

        u, v = np.meshgrid(wIdx, hIdx)

        u = u.astype(np.float)
        v = v.astype(np.float)

        x = ( u - self.pu ) * depth / self.focal
        y = ( v - self.pv ) * depth / self.focal

        coor = np.zeros((3, self.size), dtype = np.float)
        coor[0, :] = x.reshape((1, -1))
        coor[1, :] = y.reshape((1, -1))
        coor[2, :] = depth.reshape((1, -1))

        coor = self.worldRI.dot(coor)

        return coor

if __name__ == "__main__":
    _, poseIDs = load_IDs_JSON(POSE_FILENAME, POSE_NAME)
    poseData   = np.load(POSE_DATA)
    # print(poseData.shape)
    print("poseData and poseFilenames loaded.")

    # Camera.
    cam_0 = CameraBase(CAM_FOCAL, IMAGE_SIZE)
    print(cam_0.imageSize)
    print(cam_0.cameraMatrix)

    cam_1 = cam_0

    # # Test the projection of the camera.
    # X = np.array([ cam.imageSize[1], cam.imageSize[0], 2*cam.focal ]).reshape(3,1)
    # x = cam.from_camera_frame_to_image(X)
    # print(X)
    # print(x)

    # Get the pose of the first position.
    R0, t0, q0= get_pose_by_ID(POSE_ID_0, poseIDs, poseData)
    R0Inv = LA.inv(R0)

    print("t0 = \n{}".format(t0))
    print("q0 = \n{}".format(q0))
    print("R0 = \n{}".format(R0))
    print("R0Inv = \n{}".format(R0Inv))

    # Get the pose of the second position.
    R1, t1, q1 = get_pose_by_ID(POSE_ID_1, poseIDs, poseData)
    R1Inv = LA.inv(R1)

    print("t1 = \n{}".format(t1))
    print("q1 = \n{}".format(q1))
    print("R1 = \n{}".format(R1))
    print("R1Inv = \n{}".format(R1Inv))

    # Compute the rotation between the two camera poses.
    R = np.matmul( R1, R0Inv )
    print("R = \n{}".format(R))

    # Load the depth of the first image.
    depth_0 = np.load( DEPTH_DIR + "/" + POSE_ID_0 + DEPTH_SUFFIX + DEPTH_EXT )
    np.savetxt( OUT_DIR + "/depth_0.dat", depth_0, fmt="%.2e")

    # Calculate the coordinates in the first camera's frame.
    X0 = cam_0.from_depth_to_x_y(depth_0)

    output_to_ply(OUT_DIR + '/XInCam_0.ply', X0, cam_0.imageSize, DISTANCE_RANGE)

    # The coordinates in the world frame.
    XWorld_0  = R0Inv.dot(X0 - t0)
    output_to_ply(OUT_DIR + "/XInWorld_0.ply", XWorld_0, cam_1.imageSize, DISTANCE_RANGE)

    # Load the depth of the second image.
    depth_1 = np.load( DEPTH_DIR + "/" + POSE_ID_1 + DEPTH_SUFFIX + DEPTH_EXT )
    np.savetxt( OUT_DIR + "/depth_1.dat", depth_1, fmt="%.2e")

    # Calculate the coordinates in the second camera's frame.
    X1 = cam_1.from_depth_to_x_y(depth_1)

    output_to_ply(OUT_DIR + "/XInCam_1.ply", X1, cam_1.imageSize, DISTANCE_RANGE)

    # The coordiantes in the world frame.
    XWorld_1 = R1Inv.dot( X1 - t1 )
    output_to_ply(OUT_DIR + "/XInWorld_1.ply", XWorld_1, cam_1.imageSize, DISTANCE_RANGE)

    # ====================================
    # The coordinate in the seconde camera's frame.
    X_01 = R1.dot(XWorld_0) + t1
    output_to_ply(OUT_DIR + '/X_01.ply', X_01, cam_0.imageSize, DISTANCE_RANGE)

    # The image coordinates in the second camera.
    c = cam_0.from_camera_frame_to_image(X_01)

    # Get new u anv v
    u = c[0, :].reshape(cam_0.imageSize)
    v = c[1, :].reshape(cam_0.imageSize)
    np.savetxt(OUT_DIR + "/u.dat", u, fmt="%4d")
    np.savetxt(OUT_DIR + "/v.dat", v, fmt="%4d")

    # Get the du and dv.
    du, dv = du_dv(u, v, cam_0.imageSize)

    # Save.
    np.savetxt(OUT_DIR + "/du.dat", du.astype(np.int), fmt="%+3d")
    np.savetxt(OUT_DIR + "/dv.dat", dv.astype(np.int), fmt="%+3d")

    a = np.arctan2( dv, du ) / np.pi * 180

    d = np.sqrt( du * du + dv * dv )

    np.savetxt(OUT_DIR + "/a.dat", a, fmt="%+.2e")
    np.savetxt(OUT_DIR + "/d.dat", d, fmt="%+.2e")

    show(a, d, (cam_0.imageSize[0], cam_0.imageSize[1], 3))
