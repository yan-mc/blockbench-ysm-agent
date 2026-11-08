import json

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
add = json.load(open(W + r"\artifacts\v7g_add_ops.json"))["ops"]
ids = [
    # ring1 12
    "d73f6afe-6b2b-d4ed-35bd-ce4ee1169ba9", "ccee90ed-52f0-6c54-794d-2601fa6fac76",
    "48833d02-6d72-957d-0f30-83a762290076", "9e26a3f0-c134-d918-bfdc-d33fce3bf4b1",
    "4c6e5b7c-c31b-f606-e969-e854f072a790", "3d973525-f342-e1d6-ce45-f3a3040c5e06",
    "034f9132-d9bb-8789-4ebd-70ebc2ba1c35", "1ff3ac1d-365e-7c29-aa7c-f0a866b0e444",
    "dfe0eadb-ad8b-ff55-0039-24739436edb1", "9e133939-eae9-ac5b-ae58-32226e3e815e",
    "97c79da3-d273-bff2-ee00-fe5576da1a27", "219ec492-442d-2d4e-6929-acfeb472a97b",
    # ring2 16
    "c05267e4-6a0a-7529-e924-a342565c732a", "0f11ce28-152e-f95c-99a6-5d95386472ad",
    "ce3a6fad-f4a1-46d2-68cc-92f19ce8ec1c", "ff51fae0-0c16-272f-e09b-b86577b32d16",
    "aaecfced-0df5-0e28-6e4d-62284830afa1", "92051690-6043-1b31-958a-8534ab844242",
    "613fb0e9-e85d-1a06-f985-d4eb09a7deec", "6ec68123-6970-37cf-0992-eb25898dfa80",
    "55f50507-9112-d2c0-6e14-eb2353ef03e4", "4101d1c6-358c-7865-cfb2-90ec56a5f2bf",
    "b332979b-9741-1301-b654-f771c907a41a", "9cd539cc-915d-7307-4402-1cc2d614bc14",
    "21293478-386b-c8cf-bbb2-2804567bd601", "eb422750-1e7d-131e-8415-e67462e0bcaa",
    "e26c69e7-624a-943f-58a6-5eb24ec41f81", "b6da0d06-b0d5-267c-929a-3009efacc225",
    # ring3 20
    "7bc4dafe-1ed7-b0e4-d19a-41daeab9c649", "d253b1f2-f0ee-44f6-325f-085a30ab7a5c",
    "0aaceceb-73e2-9102-8d14-4fb88215fe2c", "7ac34bff-c0c9-519e-3d3f-c483c7771e8e",
    "1162d526-1090-31bd-7157-eb3ba0171051", "235102f0-bc27-2db8-47fd-1cac21ba1aa4",
    "9ef76307-c59c-36d7-353f-a4a00420b34a", "89b3c126-6d80-060c-c48f-30ab6c704703",
    "9e8a72f2-b066-cc86-07df-cec2d8aaf8de", "b1a0983d-27e0-6ec6-40cb-c30517562098",
    "817e1178-3cd7-f446-34ef-385e4a7a59ac", "beed5459-4ff5-6b35-d047-318ce24b301a",
    "6f858e30-0fb3-3e40-509f-283cba2bc20f", "ffa9a47c-999a-5462-e490-c7d4f574f447",
    "b655b41d-dd7a-5bcd-6250-e74072155f09", "ee4c34dd-c955-9583-f649-f6b879db0163",
    "2c4f465c-066d-19f5-2944-2c038966ca07", "07b24dae-1442-77c3-1181-2846c0bd4d80",
    "a8115f08-13da-6c7c-c133-690f8a6b7491", "77c932fb-15af-2b3a-15b0-c32c748a8a1d",
    # ring4 24
    "4522a862-5de9-2b4e-a8f2-7e7e1a802082", "f051c6b4-c87c-0ef6-ae0b-bc5ca9f92e01",
    "700c52d0-d2c0-e8e2-eab7-b4a9f39a7925", "034b996f-5bf2-b965-4faf-390057962919",
    "15044a78-d773-21de-04db-e4168f6124c0", "12b367fa-c912-6a79-b8c3-dfaa1d426fac",
    "c8b767e3-b9f8-90d2-6702-395cfdf87cb6", "bf3d3208-d92f-4d85-9d71-a9a890288296",
    "d572397a-d568-a90e-c4da-a29a8f120711", "3294f3ad-7a86-3087-2bc0-85f98e7bbc51",
    "c51bb8c4-a6b3-4539-30f8-1d53e306e17c", "48651453-1f5a-c503-b059-019cd9e09b60",
    "fd9fc007-5f78-9755-bfbd-10c04b72464d", "89761777-695d-98ad-0a59-bb33b088eebc",
    "d043c5c6-402c-3761-0174-fbe2a079198d", "f2391dc6-6f79-596d-7b46-a64feed17165",
    "842542e1-8664-2590-ade2-7e4180fccf37", "1c52a901-443a-568f-0c1c-d69a730fd174",
    "7d292875-8ca8-6468-98ea-e1c0c3328ef1", "54b0c036-1c1f-2470-8934-063ad95046ae",
    "a9f4e665-a48d-a07a-0225-1ffa3653335c", "03ba9896-6007-f512-35f0-917b1fa119d6",
    "f9c7539f-8e72-7c0a-7312-2b41723ed379", "2e0147fa-01f6-8bae-db1c-7f640ac8f160",
]
assert len(ids) == 72, len(ids)
ops = []
for cid, a in zip(ids, add[:72]):
    rot = a["rotation"]
    assert len(rot) == 3 and abs(rot[0]) < 1e-9
    ops.append({
        "op": "update_cube",
        "cube_id": cid,
        "rotation": [0, rot[1], -rot[2]],
        "pivot": a["pivot"],
    })
print(len(ops))
print(json.dumps({"ops": ops}, separators=(",", ":")))
