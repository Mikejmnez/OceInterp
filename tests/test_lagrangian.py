import numpy as np
import pytest

import seaduck as sd
from seaduck import utils

# Set the number of particles here.
N = int(9)

# Increase this if you want more in x direction.
skew = 3

# Change the vertical depth of the particles here.
sqrtN = int(np.sqrt(N))

# Change the horizontal range here.
x = np.append(np.linspace(-180, 180, sqrtN * skew), -37.5)
y = np.append(np.linspace(-50, -70, sqrtN // skew), -56.73891)

x, y = np.meshgrid(x, y)
x = x.ravel()
y = y.ravel()
z = None
zz = np.ones_like(x) * (-10.0)

start_time = "1992-02-01"
t = utils.convert_time(start_time) * np.ones_like(x)
end_time = "1992-02-03"
tf = utils.convert_time(end_time)


@pytest.fixture
def p():
    od = sd.OceData(utils.get_dataset("aviso"))
    return sd.Particle(
        x=x,
        y=y,
        z=z,
        t=t,
        data=od,
        # save_raw = True,
        # transport = True,
        uname="u",
        vname="v",
        wname=None,
    )


@pytest.fixture
def ecco_p():
    od = sd.OceData(utils.get_dataset("ecco"))
    return sd.Particle(x=x, y=y, z=zz, t=t, data=od, transport=True)


normal_stops = np.linspace(t[0], tf, 5)


def test_vol_mode(ecco_p):
    stops, raw = ecco_p.to_list_of_time(normal_stops=[t[0], tf])


def test_to_list_of_time(p):
    stops, raw = p.to_list_of_time(
        normal_stops=normal_stops, update_stops=[normal_stops[1]]
    )


def test_analytical_step(p):
    p.analytical_step(10.0)


def test_subset_update(p):
    np.random.seed(0)
    which = np.random.randint(1, size=p.N, dtype=bool)
    sub = p.subset(which)
    sub.lon += 1
    sub.lat += 1
    p.update_from_subset(sub, which)
    assert isinstance(sub, sd.Particle)
    assert np.allclose(p.ix[which], sub.ix)
    assert np.allclose(p.lon[which], sub.lon)


def test_subset_px_py(ecco_p):
    np.random.seed(1)
    which = np.random.randint(1, size=ecco_p.N, dtype=bool)
    ecco_p.ecco_px, ecco_p.py = ecco_p.get_px_py()
    sub = ecco_p.subset(which)
    sub.px, sub.py = sub.get_px_py()
    assert np.allclose(ecco_p.px[:, which], sub.px)
    assert np.allclose(ecco_p.py[:, which], sub.py)


@pytest.mark.parametrize("od", ["curv"], indirect=True)
def test_callback(od):
    curv_p = sd.Particle(
        y=np.array([70.5]),
        x=np.array([-14.0]),
        z=np.array([-10.0]),
        t=np.array([od.ts[0]]),
        data=od,
        uname="U",
        vname="V",
        wname="W",
        callback=lambda pt: pt.lon > -14.01,
    )
    curv_p.to_list_of_time(normal_stops=[od.ts[0], od.ts[-1]], update_stops=[])


def test_note_taking_error(p):
    with pytest.raises(AttributeError):
        p.note_taking()


def test_no_time_midp_error(p):
    with pytest.raises(AttributeError):
        p.to_list_of_time(normal_stops=[0.0, 1.0])


def test_time_out_of_bound_error(ecco_p):
    with pytest.raises(ValueError):
        ecco_p.to_list_of_time(normal_stops=[0.0, 1.0], update_stops=[])


def test_multidim_uvw_array(ecco_p):
    ecco_p.it[0] += 1
    ecco_p.update_uvw_array()


@pytest.mark.parametrize("od", ["ecco"], indirect=True)
def test_update_w_array(ecco_p, od):
    od["u0"] = od["UVELMASS"].isel(time=0)
    od["v0"] = od["VVELMASS"].isel(time=0)
    od["w0"] = od["WVELMASS"].isel(time=0)
    delattr(ecco_p, "warray")
    ecco_p.uname = "u0"
    ecco_p.vname = "v0"
    ecco_p.wname = "w0"

    ecco_p.update_uvw_array()


@pytest.mark.parametrize("od", ["ecco"], indirect=True)
def test_wall_crossing(ecco_p, od):
    od["SN"] = np.array(od["SN"])
    od["CS"] = np.array(od["CS"])
    ecco_p.ocedata.readiness["h"] = "local_cartesian"

    ecco_p._cross_cell_wall_rel()


@pytest.mark.parametrize("od", ["curv"], indirect=True)
def test_wall_crossing_no_face(od):
    od._add_missing_cs_sn()
    od.readiness["h"] = "local_cartesian"
    curv_p = sd.Particle(
        y=np.array([70.5]),
        x=np.array([-14.0]),
        z=np.array([-10.0]),
        t=np.array([od.ts[0]]),
        data=od,
        uname="U",
        vname="V",
        wname="W",
        transport=True,
    )
    curv_p._cross_cell_wall_rel()


@pytest.mark.parametrize("od", ["curv"], indirect=True)
def test_get_vol(od):
    curv_p = sd.Particle(
        y=np.array([70.5]),
        x=np.array([-14.0]),
        z=np.array([-10.0]),
        t=np.array([od.ts[0]]),
        data=od,
        uname="U",
        vname="V",
        wname="W",
        transport=True,
    )
    curv_p.get_vol()


def test_maxiteration(ecco_p):
    ecco_p.max_iteration = 1
    delattr(ecco_p, "px")
    ecco_p.to_next_stop(tf)


def test_abandon_ducks(ecco_p):
    N = len(ecco_p.izl_lin)
    ecco_p.izl_lin = (np.ones(N) * 50).astype(int)
    new_p = sd.get_masks.abandon_stuck(ecco_p)
    assert len(new_p.izl_lin) < N
