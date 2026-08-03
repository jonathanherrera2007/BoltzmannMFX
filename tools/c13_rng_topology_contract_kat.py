#!/usr/bin/env python3
"""Normative verifier for UDC-20260802-C13-RNG-TOPOLOGY-DECOMPOSITION-V1."""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path

KEY_MAGIC=b"BMXC13RNGKEYV1".ljust(16,b"\0")
RNG_FILE_MAGIC=b"BMXC13RNGLEDGV1".ljust(16,b"\0")
TOPO_FILE_MAGIC=b"BMXC13TOPLEDGV1".ljust(16,b"\0")
BATCH_MAGIC=b"BMXC13BATCHV1".ljust(16,b"\0")
STATE_MAGIC=b"BMXC13RTSTATEV1".ljust(16,b"\0")
RNG_DRAW_DOMAIN=b"BMX-C13-RNG-DRAW-V1\0"
RNG_CANDIDATES_DOMAIN=b"BMX-C13-RNG-CANDIDATES-V1\0"
RNG_RECORDS_DOMAIN=b"BMX-C13-RNG-RECORDS-V1\0"
RNG_CHAIN_INIT_DOMAIN=b"BMX-C13-RNG-CHAIN-INIT-V1\0"
RNG_CHAIN_STEP_DOMAIN=b"BMX-C13-RNG-CHAIN-STEP-V1\0"
TOPO_CANDIDATES_DOMAIN=b"BMX-C13-TOPO-CANDIDATES-V1\0"
TOPO_RECORDS_DOMAIN=b"BMX-C13-TOPO-RECORDS-V1\0"
TOPO_EVENT_ID_DOMAIN=b"BMX-C13-TOPO-EVENT-ID-V1\0"
TOPO_PROJECTION_DOMAIN=b"BMX-C13-TOPO-PROJECTION-V1\0"
TOPO_EVENT_RNG_SUBSET_DOMAIN=b"BMX-C13-TOPO-EVENT-RNG-SUBSET-V1\0"
TOPO_CHAIN_INIT_DOMAIN=b"BMX-C13-TOPO-CHAIN-INIT-V1\0"
TOPO_CHAIN_STEP_DOMAIN=b"BMX-C13-TOPO-CHAIN-STEP-V1\0"
ID_RADIX=2147483647
CPU_NAMESPACE_MAX=16777215
LOGICAL_ID_MAX=36028797002186752
AMREX_SENTINEL=549755813885
U64_MAX=0xffffffffffffffff


def ai(v):
    return int(v,0) if isinstance(v,str) and v.startswith(("0x","0X")) else int(v)

def be16(n):
    if not 0<=n<=0xffff: raise ValueError(n)
    return struct.pack(">H",n)

def be32(n):
    if not 0<=n<=0xffffffff: raise ValueError(n)
    return struct.pack(">I",n)

def be64(n):
    if not 0<=n<=U64_MAX: raise ValueError(n)
    return struct.pack(">Q",n)

def h32(s):
    b=bytes.fromhex(s)
    if len(b)!=32: raise ValueError("sha")
    return b

def fbits(x):
    return struct.unpack(">Q",struct.pack(">d",float(x)))[0]


def serialize_key(*,master_seed,seed_block,update,slot,event_type,parent,target=0,candidate=0,draw=0,retry=0):
    out=(KEY_MAGIC+struct.pack(">HBB",1,slot,event_type)+be64(master_seed)+be64(seed_block)+
         be64(update)+be64(parent)+be64(target)+be32(candidate)+be32(draw)+be32(retry)+be32(0)+be32(0))
    if len(out)!=80: raise AssertionError(len(out))
    return out


def draw_from_key(key):
    if len(key)!=80: raise ValueError("key")
    digest=hashlib.sha256(RNG_DRAW_DOMAIN+key).digest()
    raw=int.from_bytes(digest[:8],"big")
    m=raw>>11
    u=math.ldexp(float(m),-53)
    return digest,raw,m,u,fbits(u)


def identity_pair(logical_id):
    if not 1<=logical_id<=LOGICAL_ID_MAX: raise ValueError(logical_id)
    cpu=(logical_id-1)//ID_RADIX
    pid=((logical_id-1)%ID_RADIX)+1
    if not (0<=cpu<=CPU_NAMESPACE_MAX and 1<=pid<=ID_RADIX): raise AssertionError
    return pid,cpu


def serialize_candidate(*,update,slot,candidate_kind,deterministic_status,parent,target,candidate,precondition_mask,resolved_event_type,materialized_draw_count):
    out=struct.pack(">QBBHQQIQBBHI",update,slot,candidate_kind,deterministic_status,parent,target,candidate,precondition_mask,resolved_event_type,materialized_draw_count,0,0)
    if len(out)!=48: raise AssertionError(len(out))
    return out


def event_id_preimage(*,slot,event_type,update,parent,target,candidate,children):
    if not 0<=len(children)<=255: raise ValueError("children")
    return (TOPO_EVENT_ID_DOMAIN+struct.pack(">HBBQQQIB3x",1,slot,event_type,update,parent,target,candidate,len(children))+
            b"".join(be64(x) for x in children))

def event_id(**kwargs):
    pre=event_id_preimage(**kwargs)
    return pre,hashlib.sha256(pre).digest()


def serialize_projection(v):
    n=ai(v["n_bnds"]); bonds=v["bonds"]
    if not 0<=n<=4 or len(bonds)!=4: raise ValueError("bonds")
    active=[tuple(ai(x) for x in b) for b in bonds[:n]]
    if any(b[0]==0 for b in active) or active!=sorted(active): raise ValueError("bond order")
    if any(any(ai(x)!=0 for x in b) for b in bonds[n:]): raise ValueError("bond padding")
    scalars=[ai(x) for x in v["scalar_bits"]]
    if len(scalars)!=13: raise ValueError("scalars")
    out=struct.pack(">QIIiiIiiiiIQ",ai(v["logical_id"]),ai(v["amrex_id"]),ai(v["cpu_namespace"]),ai(v["cell_type"]),ai(v["position"]),n,ai(v["fuse_flag"]),ai(v["split_flag"]),ai(v["fuse_tip"]),ai(v["fix_site"]),ai(v["projection_flags"]),ai(v["target"]))
    out+=be64(ai(v["tau_bits"]))+b"".join(be64(x) for x in scalars)
    out+=b"".join(struct.pack(">Qii",ai(b[0]),ai(b[1]),ai(b[2])) for b in bonds)+bytes(24)
    if len(out)!=256: raise AssertionError(len(out))
    return out


def projection_hash(records):
    if any(len(x)!=256 for x in records): raise ValueError("projection size")
    ids=[int.from_bytes(x[:8],"big") for x in records]
    if ids!=sorted(ids) or len(ids)!=len(set(ids)): raise ValueError("projection order")
    return hashlib.sha256(TOPO_PROJECTION_DOMAIN+be32(len(records))+b"".join(records)).digest()


def candidate_digest(domain,records):
    if any(len(x)!=48 for x in records): raise ValueError("candidate")
    return hashlib.sha256(domain+b"".join(records)).digest()

def records_digest(domain,records,size):
    if any(len(x)!=size for x in records): raise ValueError("record")
    return hashlib.sha256(domain+b"".join(records)).digest()

def event_rng_subset_hash(records):
    if any(len(x)!=208 for x in records): raise ValueError("rng subset")
    return hashlib.sha256(TOPO_EVENT_RNG_SUBSET_DOMAIN+be32(len(records))+b"".join(records)).digest()


def serialize_rng_record(v):
    key=bytes.fromhex(v["key_hex"]); digest=bytes.fromhex(v["digest_hex"])
    out=(b"RNG1"+be16(1)+bytes([ai(v["event_type"]),ai(v["slot"])])+be64(ai(v["update"]))+
         be64(ai(v["time_bits"]))+be64(ai(v["parent"]))+be64(ai(v["target"]))+be32(ai(v["candidate"]))+
         be32(ai(v["draw"]))+be32(ai(v["retry"]))+be16(ai(v["use_code"]))+bytes([ai(v["draw_status"]),ai(v["decision_code"])])+
         be64(ai(v["threshold_bits"]))+key+digest+be64(ai(v["raw_uint64"]))+be64(ai(v["uniform_bits"]))+
         be64(ai(v["event_plan_ordinal"]))+be64(0))
    if len(out)!=208: raise AssertionError(len(out))
    dg,raw,_,_,ub=draw_from_key(key)
    if dg!=digest or raw!=ai(v["raw_uint64"]) or ub!=ai(v["uniform_bits"]): raise ValueError("rng record consistency")
    return out


def serialize_topology_record(v):
    pred=[ai(x) for x in v["predecessors"]]; succ=[ai(x) for x in v["successors"]]; children=[ai(x) for x in v["children"]]
    if not (len(pred)==4 and len(succ)==4 and len(children)==2): raise ValueError("id arrays")
    pa=[ai(x) for x in v["pre_amount_bits"]]; sa=[ai(x) for x in v["post_amount_bits"]]; rr=[ai(x) for x in v["residual_bits"]]
    if not (len(pa)==len(sa)==len(rr)==3): raise ValueError("amounts")
    out=(b"TOP1"+be16(1)+bytes([ai(v["event_type"]),ai(v["slot"])])+be64(ai(v["update"]))+be64(ai(v["time_bits"]))+
         be64(ai(v["event_ordinal"]))+be32(ai(v["candidate"]))+bytes([ai(v["predecessor_count"]),ai(v["successor_count"]),ai(v["child_count"]),ai(v["flags"])])+
         be64(ai(v["parent"]))+be64(ai(v["target"]))+h32(v["event_id_hex"])+h32(v["pre_topology_hex"])+h32(v["post_topology_hex"])+h32(v["config_hex"])+
         be16(ai(v["destination_code"]))+be16(ai(v["reason_code"]))+be32(0)+b"".join(be64(x) for x in pred)+b"".join(be64(x) for x in succ)+b"".join(be64(x) for x in children)+
         b"".join(be64(x) for x in pa)+b"".join(be64(x) for x in sa)+b"".join(be64(x) for x in rr)+h32(v["rng_subset_hex"])+be64(0))
    if len(out)!=384: raise AssertionError(len(out))
    return out


def chain_init(domain,contract_sha,seed,block,network_sha,config_sha):
    return hashlib.sha256(domain+h32(contract_sha)+be64(seed)+be64(block)+h32(network_sha)+h32(config_sha)).digest()

def chain_step(domain,previous,*,kind,slot,update,time_bits,candidate_count,candidate_digest_value,record_count,records_digest_value,cumulative_record_count):
    core=struct.pack(">HBBQQQ",1,kind,slot,update,time_bits,candidate_count)+candidate_digest_value+be64(record_count)+records_digest_value
    if len(core)!=100: raise AssertionError(len(core))
    return hashlib.sha256(domain+previous+core+be64(cumulative_record_count)).digest()


def serialize_file_header(*,kind,contract_sha,network_sha,config_sha,start_update):
    magic=RNG_FILE_MAGIC if kind==1 else TOPO_FILE_MAGIC if kind==2 else None
    if magic is None: raise ValueError(kind)
    out=magic+be16(1)+bytes([kind,1])+h32(contract_sha)+h32(network_sha)+h32(config_sha)+be64(start_update)+be32(0)
    if len(out)!=128: raise AssertionError(len(out))
    return out


def serialize_batch_header(*,kind,slot,update,time_bits,candidate_count,candidate_digest_hex,record_count,records_digest_hex,previous_chain_hex,new_chain_hex,cumulative_record_count):
    out=(BATCH_MAGIC+be16(1)+bytes([kind,slot])+be64(update)+be64(time_bits)+be64(candidate_count)+h32(candidate_digest_hex)+be64(record_count)+h32(records_digest_hex)+h32(previous_chain_hex)+h32(new_chain_hex)+be64(cumulative_record_count)+be32(0))
    if len(out)!=192: raise AssertionError(len(out))
    return out


def serialize_state(v):
    out=(STATE_MAGIC+be16(1)+be16(1)+h32(v["contract_sha"])+h32(v["network_sha"])+h32(v["config_sha"])+
         be64(ai(v["master_seed"]))+be64(ai(v["seed_block"]))+be64(ai(v["next_update"]))+be64(ai(v["next_logical_id"]))+
         be64(ai(v["completed_o06"]))+be64(ai(v["completed_o08"]))+be64(ai(v["candidate_count"]))+be64(ai(v["rng_record_count"]))+
         be64(ai(v["topology_record_count"]))+be64(ai(v["child_count"]))+be64(ai(v["time_bits"]))+h32(v["rng_chain_hex"])+h32(v["topology_chain_hex"])+
         be64(AMREX_SENTINEL)+be64(ai(v["last_completed_update"]))+bytes(36))
    if len(out)!=320: raise AssertionError(len(out))
    return out


def verify(path):
    d=json.loads(path.read_text(encoding="utf-8"))
    contract_path=path.with_name("RNG_TOPOLOGY_DECOMPOSITION_CONTRACT_V1.json")
    if hashlib.sha256(contract_path.read_bytes()).hexdigest()!=d["contract_sha256"]: raise SystemExit("contract hash")
    for v in d["draw_vectors"]:
        inp={k:ai(x) for k,x in v["input"].items()}; key=serialize_key(**inp); dg,raw,m,u,bits=draw_from_key(key)
        got={"key_hex":key.hex(),"digest_hex":dg.hex(),"raw_uint64":str(raw),"mantissa53":str(m),"uniform_bits_hex":f"0x{bits:016x}","uniform_hex":u.hex()}
        if got!=v["expected"]: raise SystemExit("draw "+v["id"])
    for v in d["identity_vectors"]:
        pid,cpu=identity_pair(ai(v["logical_id"]))
        if pid!=ai(v["amrex_id"]) or cpu!=ai(v["cpu_namespace"]): raise SystemExit("identity")
    cv=d["candidate_descriptor_vector"]; cb=serialize_candidate(**{k:ai(x) for k,x in cv["input"].items()})
    if cb.hex()!=cv["expected"]["descriptor_hex"]: raise SystemExit("candidate bytes")
    if candidate_digest(RNG_CANDIDATES_DOMAIN,[cb]).hex()!=cv["expected"]["rng_digest_hex"]: raise SystemExit("rng candidate")
    if candidate_digest(TOPO_CANDIDATES_DOMAIN,[cb]).hex()!=cv["expected"]["topology_digest_hex"]: raise SystemExit("topo candidate")
    for v in d["event_id_vectors"]:
        inp={k:([ai(y) for y in x] if k=="children" else ai(x)) for k,x in v["input"].items()}; pre,dg=event_id(**inp)
        if pre.hex()!=v["expected"]["preimage_hex"] or dg.hex()!=v["expected"]["event_id_hex"]: raise SystemExit("event id")
    pv=d["projection_hash_vector"]; prs=[serialize_projection(x) for x in pv["input"]["records"]]
    if [x.hex() for x in prs]!=pv["expected"]["record_hex"] or projection_hash(prs).hex()!=pv["expected"]["projection_hash_hex"]: raise SystemExit("projection")
    rv=d["rng_record_vector"]; rb=serialize_rng_record(rv["input"])
    if rb.hex()!=rv["expected"]["record_hex"]: raise SystemExit("rng record")
    if event_rng_subset_hash([rb]).hex()!=rv["expected"]["event_rng_subset_hex"]: raise SystemExit("rng subset")
    tv=d["topology_record_vector"]; tb=serialize_topology_record(tv["input"])
    if tb.hex()!=tv["expected"]["record_hex"]: raise SystemExit("topology record")
    ci=d["chain_init_vector"]
    for name,domain in (("rng",RNG_CHAIN_INIT_DOMAIN),("topology",TOPO_CHAIN_INIT_DOMAIN)):
        i=ci["input"]; got=chain_init(domain,i["contract_sha256"],ai(i["master_seed"]),ai(i["seed_block"]),i["initial_network_sha256"],i["generated_configuration_sha256"]).hex()
        if got!=ci["expected"][name+"_chain_hex"]: raise SystemExit("chain init")
    for v in d["ledger_vectors"]:
        kind=1 if v["ledger_kind"]=="RNG" else 2; size=208 if kind==1 else 384
        cd_domain=RNG_CANDIDATES_DOMAIN if kind==1 else TOPO_CANDIDATES_DOMAIN
        rd_domain=RNG_RECORDS_DOMAIN if kind==1 else TOPO_RECORDS_DOMAIN
        step_domain=RNG_CHAIN_STEP_DOMAIN if kind==1 else TOPO_CHAIN_STEP_DOMAIN
        desc=[bytes.fromhex(x) for x in v["input"]["candidate_descriptors_hex"]]; rec=[bytes.fromhex(x) for x in v["input"]["records_hex"]]
        cd=candidate_digest(cd_domain,desc); rd=records_digest(rd_domain,rec,size)
        if cd.hex()!=v["expected"]["candidate_digest_hex"] or rd.hex()!=v["expected"]["records_digest_hex"]: raise SystemExit("ledger digest")
        new=chain_step(step_domain,h32(v["input"]["previous_chain_hex"]),kind=kind,slot=ai(v["input"]["slot"]),update=ai(v["input"]["update"]),time_bits=ai(v["input"]["time_bits"]),candidate_count=len(desc),candidate_digest_value=cd,record_count=len(rec),records_digest_value=rd,cumulative_record_count=ai(v["input"]["cumulative_record_count"]))
        if new.hex()!=v["expected"]["new_chain_hex"]: raise SystemExit("chain step")
        fh=serialize_file_header(kind=kind,contract_sha=d["contract_sha256"],network_sha=d["chain_init_vector"]["input"]["initial_network_sha256"],config_sha=d["chain_init_vector"]["input"]["generated_configuration_sha256"],start_update=0)
        if fh.hex()!=v["expected"]["file_header_hex"]: raise SystemExit("file header")
        bh=serialize_batch_header(kind=kind,slot=ai(v["input"]["slot"]),update=ai(v["input"]["update"]),time_bits=ai(v["input"]["time_bits"]),candidate_count=len(desc),candidate_digest_hex=cd.hex(),record_count=len(rec),records_digest_hex=rd.hex(),previous_chain_hex=v["input"]["previous_chain_hex"],new_chain_hex=new.hex(),cumulative_record_count=ai(v["input"]["cumulative_record_count"]))
        if bh.hex()!=v["expected"]["batch_header_hex"]: raise SystemExit("batch header")
    sv=d["state_vector"]; sb=serialize_state(sv["input"])
    if sb.hex()!=sv["expected"]["state_hex"] or hashlib.sha256(sb).hexdigest()!=sv["expected"]["state_sha256"]: raise SystemExit("state")
    print("PASS: contract SHA; 6 draws; 4 identities; candidate; 3 event IDs; projection; RNG/topology records; event subset; 2 chain inits; 2 file/batch/chain vectors; checkpoint state")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("kat",type=Path); args=ap.parse_args(); verify(args.kat)
if __name__=="__main__": main()
