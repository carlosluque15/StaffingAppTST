import { useEffect, useState } from "react";
import accentureLogo from "./assets/toppng.com-accenture-logo-transparent-accenture-greater-than-logo-370x385.png";
import "./App.css";

const navigation = [
  { id: "home", label: "Inicio", icon: "home" },
  { id: "demands", label: "Demandas", icon: "briefcase" },
  { id: "talent", label: "Talento", icon: "users" },
  { id: "mentors", label: "Mentores", icon: "users" },
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestApi(path, options) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/${path}`, options);
  } catch {
    throw new Error("No se pudo conectar con la API.");
  }
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON body: fall back to the HTTP status below.
  }
  if (!response.ok) {
    const error = new Error(
      data?.message || data?.error || `La API respondió con HTTP ${response.status}.`,
    );
    error.code = data?.error;
    throw error;
  }
  return data;
}

function Icon({ name, size = 20 }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7" /><path d="M5 9v11h14V9M9 20v-6h6v6" /></>,
    briefcase: <><rect x="3" y="7" width="18" height="14" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="10" cy="7" r="4" /><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    filter: <><path d="M4 7h16M7 12h10M10 17h4" /><circle cx="8" cy="7" r="1.5" /><circle cx="15" cy="12" r="1.5" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15" /></>,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    sparkle: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2z" /><path d="m19 14 1 2.5 2.5 1-2.5 1L19 21l-1-2.5-2.5-1 2.5-1z" /></>,
  };

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

function Brand({ compact = false }) {
  return (
    <div className={`brand ${compact ? "brand-compact" : ""}`}>
      <img className="brand-logo" src={accentureLogo} alt="" />
      {!compact && (
        <span className="brand-name">
          accenture<span>staffing</span>
        </span>
      )}
    </div>
  );
}

function Sidebar({ page, setPage, demandCount }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand"><Brand /></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="side-nav" aria-label="Navegación principal">
        {navigation.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${page === item.id ? "active" : ""}`}
            onClick={() => setPage(item.id)}
          >
            <Icon name={item.icon} size={19} />
            <span>{item.label}</span>
            {item.id === "demands" && <span className="nav-count">{demandCount}</span>}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-help">
          <div className="help-spark"><Icon name="sparkle" size={18} /></div>
          <strong>¿Necesitas ayuda?</strong>
          <p>Estamos aquí para ayudarte a encontrar el mejor talento.</p>
          <button onClick={() => window.alert("Contacta con el equipo de Staffing.")}>
            Contactar equipo <Icon name="arrow" size={15} />
          </button>
        </div>
        <div className="sidebar-profile">
          <div className="profile-avatar">ST</div>
          <div className="profile-copy">
            <strong>Staffing</strong>
            <span>Workspace</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ title, onNewDemand }) {
  return (
    <header className="topbar">
      <div className="breadcrumb"><span>Staffing workspace</span><Icon name="chevron" size={15} /><strong>{title}</strong></div>
      <div className="topbar-actions">
        <span className="demo-pill"><i /> Acceso sin inicio de sesión</span>
        <button className="button button-purple button-small" onClick={onNewDemand}>
          <Icon name="plus" size={17} /> Nueva demanda
        </button>
      </div>
    </header>
  );
}

function Dashboard({ demands, candidates, setPage, onNewDemand, onOpenDemand }) {
  const coveredDemands = demands.filter((demand) =>
    /cubierta|covered/i.test(demand.status),
  ).length;

  return (
    <>
      <section className="welcome-banner">
        <div className="welcome-copy">
          <p className="eyebrow eyebrow-light">STAFFING WORKSPACE</p>
          <h1>Bienvenido <span className="wave">✦</span></h1>
          <p>Hagamos que el talento correcto encuentre su próximo reto.</p>
          <button className="button button-white" onClick={onNewDemand}>
            <Icon name="plus" size={17} /> Crear una demanda
          </button>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-glow" />
          <div className="art-orbit art-orbit-a" />
          <div className="art-orbit art-orbit-b" />
          <div className="art-star">✳</div>
          <div className="art-bubble bubble-one">Ideas</div>
          <div className="art-bubble bubble-two">Talento</div>
          <div className="art-bubble bubble-three">Impacto</div>
        </div>
      </section>

      <div className="section-title-row">
        <div><p className="eyebrow">Tu actividad</p><h2>Todo en un mismo lugar</h2></div>
        <button className="text-link" onClick={() => setPage("demands")}>
          Ver actividad <Icon name="arrow" size={16} />
        </button>
      </div>

      <section className="metric-grid" aria-label="Resumen">
        <article className="metric-card">
          <span className="metric-icon metric-purple"><Icon name="briefcase" /></span>
          <span className="metric-label">Demandas activas</span>
          <div className="metric-value">{demands.filter((demand) => !["Cubierta", "Cancelada"].includes(demand.status)).length}</div>
          <span className="metric-foot">En búsqueda de talento</span>
        </article>
        <article className="metric-card">
          <span className="metric-icon metric-orange"><Icon name="users" /></span>
          <span className="metric-label">Perfiles en base de datos</span>
          <div className="metric-value">{candidates.length}</div>
          <span className="metric-foot">Candidatos en la base de datos</span>
        </article>
        <article className="metric-card">
          <span className="metric-icon metric-green"><Icon name="check" /></span>
          <span className="metric-label">Demandas cubiertas</span>
          <div className="metric-value">{coveredDemands}</div>
          <span className="metric-foot">Marcadas como cubiertas</span>
        </article>
      </section>

      <div className="section-title-row recent-title">
        <div><p className="eyebrow">En movimiento</p><h2>Demandas recientes</h2></div>
        <button className="text-link" onClick={() => setPage("demands")}>
          Ver todas <Icon name="arrow" size={16} />
        </button>
      </div>
      <DemandTable demands={demands.slice(0, 3)} onOpenDemand={onOpenDemand} />

      <section className="insight-banner">
        <div className="insight-icon"><Icon name="sparkle" size={21} /></div>
        <div><strong>Un buen match empieza con una buena demanda.</strong><p>Cuanto más claro el perfil, más rápido encontrarás a la persona adecuada.</p></div>
        <button className="text-link" onClick={onNewDemand}>Crear demanda <Icon name="arrow" size={16} /></button>
      </section>
    </>
  );
}

function DemandTable({ demands, onOpenDemand }) {
  if (!demands.length) {
    return (
      <div className="empty-state">
        <span className="empty-icon"><Icon name="briefcase" size={24} /></span>
        <strong>Aún no hay demandas</strong>
        <p>Crea una demanda para empezar a buscar talento.</p>
      </div>
    );
  }

  return (
    <div className="table-card">
      <div className="demand-table-wrap">
        <table className="demand-table">
          <thead><tr><th>DEMANDA</th><th>LOCALIZACIÓN</th><th>FECHA DE INICIO</th><th>ESTADO</th><th /></tr></thead>
          <tbody>
            {demands.map((demand) => (
              <tr key={demand.id} onClick={() => onOpenDemand(demand)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && onOpenDemand(demand)}>
                <td><span className="demand-mini-icon"><Icon name="briefcase" size={17} /></span><span className="demand-name"><strong>{demand.title}</strong><small>{demand.id} · {demand.role}</small></span></td>
                <td>{demand.location}</td><td>{formatDate(demand.startDate)}</td>
                <td><span className="status-pill"><i />{demand.status}</span></td>
                <td><button className="row-arrow" aria-label={`Abrir ${demand.title}`}><Icon name="chevron" size={17} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DemandForm({ catalog, onCancel, onSubmit, demand = null }) {
  const editing = Boolean(demand);
  const [form, setForm] = useState(demand ? { ...demand, skills: demand.skills.join(", ") } : {
    title: "",
    role: "",
    skills: "",
    seniority: "",
    industry: "",
    offering: "",
    availability: "Inmediata",
    occupancy: "100%",
    location: "",
    modality: "Híbrido",
    startDate: "",
    duration: "6 meses",
    description: "",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!form.title.trim() || !form.role.trim() || !form.seniority || !form.industry || !form.offering || !form.location || !form.startDate) {
      setError("Completa el título, rol, nivel, industria, offering, localización y fecha de inicio.");
      return;
    }
    if (!form.skills.trim()) {
      setError("Añade al menos una habilidad para orientar la búsqueda.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await onSubmit({
        ...form,
        skills: form.skills.split(",").map((skill) => skill.trim()).filter(Boolean),
      });
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="form-page">
      <div className="page-heading">
        <div><p className="eyebrow">{editing ? `Editar · ${demand.id}` : "Nueva búsqueda"}</p><h1>{editing ? "Editar demanda" : "Crear demanda"}</h1><p>{editing ? "Modifica los datos de la demanda; los candidatos se recalcularán con los nuevos criterios." : "Cuéntanos qué perfil necesita tu proyecto. Cuanto más detalle, mejor será la búsqueda."}</p></div>
        <span className="form-step"><b>1</b> Información del perfil <i /> <b className="step-inactive">2</b> Resultados</span>
      </div>
      <form className="demand-form" onSubmit={submit}>
        <div className="form-section-heading"><span className="form-section-number">01</span><div><h2>Sobre la demanda</h2><p>Información general del rol y el proyecto.</p></div></div>
        <div className="form-grid">
          <label className="field field-full"><span>Nombre de la demanda <b>*</b></span><input value={form.title} onChange={(e) => update("title", e.target.value)} placeholder="Ej. Data Engineer para proyecto de banca" /></label>
          <label className="field"><span>Rol o perfil <b>*</b></span><input value={form.role} onChange={(e) => update("role", e.target.value)} placeholder="Ej. Data Engineer" /></label>
          <label className="field"><span>Nivel (career level) <b>*</b></span><select value={form.seniority} onChange={(e) => update("seniority", e.target.value)}><option value="">Selecciona un nivel</option>{catalog.levels.map((level) => <option key={level.name}>{level.name}</option>)}</select></label>
          <label className="field"><span>Industria <b>*</b></span><select value={form.industry} onChange={(e) => update("industry", e.target.value)}><option value="">Selecciona una industria</option>{catalog.industries.map((industry) => <option key={industry}>{industry}</option>)}</select></label>
          <label className="field"><span>Área / offering <b>*</b></span><select value={form.offering} onChange={(e) => update("offering", e.target.value)}><option value="">Selecciona un offering</option>{catalog.areas.map((area) => <option key={area}>{area}</option>)}</select></label>
          <label className="field"><span>Disponibilidad requerida</span><select value={form.availability} onChange={(e) => update("availability", e.target.value)}><option>Inmediata</option><option>2 semanas</option><option>1 mes</option><option>3 meses</option><option>Flexible</option></select></label>
          <label className="field"><span>Porcentaje de ocupación</span><select value={form.occupancy} onChange={(e) => update("occupancy", e.target.value)}><option>100%</option><option>80%</option><option>60%</option><option>50%</option>{!["100%", "80%", "60%", "50%", "Flexible"].includes(form.occupancy) && <option>{form.occupancy}</option>}<option>Flexible</option></select></label>
          <label className="field"><span>Localización <b>*</b></span><select value={form.location} onChange={(e) => update("location", e.target.value)}><option value="">Selecciona una ciudad</option>{catalog.locations.map((city) => <option key={city.value}>{city.value}</option>)}<option>Remoto</option></select></label>
          <label className="field"><span>Modalidad</span><select value={form.modality} onChange={(e) => update("modality", e.target.value)}><option>Híbrido</option><option>Presencial</option><option>Remoto</option></select></label>
        </div>

        <div className="form-section-heading form-section-spaced"><span className="form-section-number">02</span><div><h2>Requisitos y habilidades</h2><p>¿Qué necesita saber o haber hecho esta persona?</p></div></div>
        <div className="form-grid">
          <label className="field field-full"><span>Habilidades clave <b>*</b></span><input value={form.skills} onChange={(e) => update("skills", e.target.value)} placeholder="Ej. Azure, Python, Databricks, SQL" /><small>Separa las habilidades con comas.</small></label>
          <label className="field"><span>Fecha de inicio <b>*</b></span><input type="date" value={form.startDate} onChange={(e) => update("startDate", e.target.value)} /></label>
          <label className="field"><span>Duración estimada</span><select value={form.duration} onChange={(e) => update("duration", e.target.value)}><option>3 meses</option><option>6 meses</option><option>9 meses</option><option>12 meses</option><option>Indefinida</option></select></label>
          <label className="field field-full"><span>Descripción del proyecto</span><textarea rows="4" value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Contexto, responsabilidades y cualquier detalle que ayude a encontrar el perfil adecuado..." /></label>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="form-footer"><p><b>*</b> Campos obligatorios</p><div><button className="button button-quiet" type="button" onClick={onCancel} disabled={saving}>Cancelar</button><button className="button button-purple" type="submit" disabled={saving}>{saving ? "Guardando..." : editing ? "Guardar cambios" : "Guardar y ver candidatos"} {!saving && <Icon name="arrow" size={17} />}</button></div></div>
      </form>
    </div>
  );
}

const STAGE_LABELS = { initial: "Offering inicial", expanded: "Resto de offerings", transversal: "Bolsa transversal" };

function formatPercent(value) {
  return value === null || value === undefined ? "N/D" : `${value}%`;
}

function ResultsPage({ demand, onBack, onOpenCandidate, onDemandChanged, onComplete }) {
  const [stage, setStage] = useState("initial");
  const [result, setResult] = useState({ key: "", search: null, selections: [], error: null });
  const [actionError, setActionError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [query, setQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const demandId = demand?.id;
  const demandClosed = demand ? ["Cubierta", "Cancelada"].includes(demand.status) : false;

  const requestKey = `${demandId}|${stage}|${reloadKey}`;
  useEffect(() => {
    if (!demandId) return undefined;
    let active = true;
    Promise.all([
      requestApi(`demands/${encodeURIComponent(demandId)}/search/?stage=${stage}`),
      requestApi(`demands/${encodeURIComponent(demandId)}/candidates/`),
    ])
      .then(([searchData, selectionData]) => {
        if (active) setResult({ key: requestKey, search: searchData, selections: selectionData.candidates, error: null });
      })
      .catch((requestError) => {
        if (active) setResult({ key: requestKey, search: null, selections: [], error: requestError });
      });
    return () => { active = false; };
  }, [demandId, stage, requestKey]);
  const loading = Boolean(demandId) && result.key !== requestKey;
  const { search, selections, error } = result;

  async function toggleSelection(candidate, selected) {
    setActionError("");
    setBusyId(candidate.id);
    try {
      const base = `demands/${encodeURIComponent(demandId)}/candidates/`;
      if (selected) {
        await requestApi(`${base}${encodeURIComponent(candidate.id)}/`, { method: "DELETE" });
      } else {
        await requestApi(base, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ staffId: candidate.id }),
        });
      }
      setReloadKey((key) => key + 1);
      await onDemandChanged(demandId);
    } catch (requestError) {
      setActionError(requestError.message);
    } finally {
      setBusyId("");
    }
  }

  const selectedIds = new Set(selections.map((selection) => selection.id));
  const text = query.trim().toLowerCase();
  const matchesText = (candidate) =>
    !text || `${candidate.name} ${candidate.role} ${candidate.id}`.toLowerCase().includes(text);
  const visibleCandidates = (search?.candidates ?? []).filter(matchesText);
  const transversalCandidates = (search?.transversal.candidates ?? []).filter(matchesText);
  const mappingMissing = error?.code === "offering_mapping_missing";

  if (!demand) {
    return (
      <div className="results-page">
        <div className="empty-state"><span className="empty-icon"><Icon name="briefcase" size={24} /></span><strong>Selecciona una demanda</strong><p>Crea o abre una demanda para ver candidatos.</p><button className="button button-purple" onClick={onBack}>Ir a demandas</button></div>
      </div>
    );
  }

  return (
    <div className="results-page">
      <div className="results-back-row"><button className="back-link" onClick={onBack}>‹ Volver a demandas</button><span className="demo-pill"><i /> Perfiles de la base de datos</span></div>
      <div className="results-page-heading">
        <div><p className="eyebrow">Búsqueda de talento · {demand.id}</p><h1>{demand.title}</h1><p>{demand.role} <span className="dot-separator">·</span> {demand.location} <span className="dot-separator">·</span> {demand.seniority} <span className="dot-separator">·</span> {demand.status}</p></div>
      </div>
      <div className="search-insight"><span className="insight-icon"><Icon name="filter" size={19} /></span><p><strong>Filtrado por datos, sin puntuación.</strong> La exportación de Staff no incluye habilidades, por lo que no se calcula afinidad ni se ordena por encaje. Los perfiles aparecen en orden alfabético.</p></div>
      <div className="search-stage">
        <div className="stage-flow">
          <span className={`stage-number ${stage === "initial" ? "stage-active" : "stage-complete"}`}>{stage === "initial" ? "01" : <Icon name="check" size={14} />}</span>
          <span className={stage === "initial" ? "stage-label stage-label-active" : "stage-label"}>Offering inicial <strong>{demand.offering}</strong></span>
          <i />
          <span className={`stage-number ${stage === "expanded" ? "stage-active" : ""}`}>02</span>
          <span className={stage === "expanded" ? "stage-label stage-label-active" : "stage-label"}>Resto de offerings</span>
        </div>
        <button className="text-link stage-action" onClick={() => setStage((current) => current === "initial" ? "expanded" : "initial")} disabled={loading}>
          {stage === "expanded" ? "Volver al offering inicial" : "Ampliar búsqueda"} <Icon name="arrow" size={15} />
        </button>
      </div>
      {demandClosed && <p className="form-error" role="status">La demanda está {demand.status.toLowerCase()}: las selecciones están cerradas.</p>}
      {actionError && <p className="form-error" role="alert">{actionError}</p>}

      <section className="proposal-panel" aria-label="Candidatos seleccionados">
        <h2>Candidatos seleccionados <span>{selections.length}</span></h2>
        {selections.length === 0 ? <p>Aún no has seleccionado a nadie. Pulsa «Seleccionar» en un candidato; cuando tengas a la persona elegida, pulsa «Completar demanda» para asignarla al proyecto.</p> : (
          <ul>
            {selections.map((selection) => (
              <li key={selection.id}>
                <span><strong>{selection.name}</strong> · {selection.role || "Sin rol"} · {STAGE_LABELS[selection.searchStage]}</span>
                <button className="text-link" disabled={busyId === selection.id || demandClosed} onClick={() => toggleSelection(selection, true)}>Retirar</button>
              </li>
            ))}
          </ul>
        )}
        {!demandClosed && <button className="button button-purple" disabled={selections.length === 0} onClick={() => onComplete(demand)}>Completar demanda <Icon name="arrow" size={16} /></button>}
      </section>

      <div className="results-toolbar">
        <label className="search-box"><Icon name="search" size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filtra por nombre, rol o ID" aria-label="Filtrar resultados" /></label>
      </div>

      {loading && <p className="api-note" role="status">Buscando candidatos...</p>}
      {!loading && error && (
        <div className="empty-state" role="alert">
          <span className="empty-icon"><Icon name="close" size={24} /></span>
          <strong>{mappingMissing ? "Falta definir la correspondencia del offering" : "No se pudo completar la búsqueda"}</strong>
          <p>{error.message}</p>
          <button className="button button-outline" onClick={() => setReloadKey((key) => key + 1)}>Reintentar</button>
        </div>
      )}
      {!loading && search && (
        <>
          <ul className="criteria-list" aria-label="Criterios aplicados">
            {search.criteria.map((criterion) => (
              <li key={criterion.criterion} className={criterion.applied ? "criterion-on" : "criterion-off"}>
                <strong>{criterion.criterion}</strong>: {criterion.applied ? "aplicado" : "no aplicado"}{criterion.detail ? ` — ${criterion.detail}` : ""}
              </li>
            ))}
          </ul>
          <div className="results-count-row"><p><strong>{visibleCandidates.length} perfiles</strong> encontrados <span>· {STAGE_LABELS[stage]}{Object.keys(search.excluded).length ? ` · excluidos: ${Object.entries(search.excluded).map(([reason, count]) => `${reason} ${count}`).join(", ")}` : ""}</span></p></div>
          <div className="candidate-list">
            {visibleCandidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                candidate={candidate}
                saved={selectedIds.has(candidate.id)}
                busy={busyId === candidate.id}
                disabled={demandClosed}
                onToggleSave={() => toggleSelection(candidate, selectedIds.has(candidate.id))}
                onOpen={() => onOpenCandidate(candidate)}
              />
            ))}
            {visibleCandidates.length === 0 && <div className="empty-state"><span className="empty-icon"><Icon name="search" size={24} /></span><strong>{text ? "Ningún perfil coincide con el filtro" : stage === "initial" ? `No hay perfiles disponibles en ${demand.offering}` : "No hay perfiles disponibles en otros offerings"}</strong><p>{stage === "initial" ? "Puedes ampliar la búsqueda al resto de offerings." : "Revisa los criterios aplicados y los excluidos."}</p></div>}
          </div>
          <section className="transversal-section" aria-label="Bolsa transversal">
            <h2>Bolsa transversal <span>{transversalCandidates.length}</span></h2>
            <p>Personas sin offering asignado en los datos. Aparecen en todas las búsquedas, en cualquier etapa.</p>
            <div className="candidate-list">
              {transversalCandidates.map((candidate) => (
                <CandidateCard
                  key={candidate.id}
                  candidate={candidate}
                  saved={selectedIds.has(candidate.id)}
                  busy={busyId === candidate.id}
                  disabled={demandClosed}
                  onToggleSave={() => toggleSelection(candidate, selectedIds.has(candidate.id))}
                  onOpen={() => onOpenCandidate(candidate)}
                />
              ))}
              {transversalCandidates.length === 0 && <p className="api-note">No hay personas disponibles en la bolsa transversal con estos criterios.</p>}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function initialsOf(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "ST";
}

function CandidateCard({ candidate, saved, busy, disabled, onToggleSave, onOpen }) {
  const unit = [candidate.organizationUnit, candidate.talentSegment].filter(Boolean).join(" · ");
  return (
    <article className="candidate-card">
      <button className="candidate-main" onClick={onOpen} aria-label={`Ver perfil de ${candidate.name}`}>
        <div className="candidate-avatar avatar-lilac">{initialsOf(candidate.name)}<i /></div>
        <div className="candidate-info">
          <div className="candidate-name-row"><h2>{candidate.name}</h2><span className="candidate-id">{candidate.id}</span></div>
          <p className="candidate-role">{candidate.role || "Sin rol indicado"} <span>·</span> {candidate.careerLevel || "Nivel no indicado"}</p>
          <div className="candidate-meta"><span><Icon name="map" size={15} />{candidate.location || "Sin ubicación"}</span><span><Icon name="clock" size={15} />FTE {candidate.resourceFte || "N/D"} · libre {formatPercent(candidate.availablePercent)}</span><span><Icon name="briefcase" size={14} />{unit || "Sin offering"}</span></div>
          {candidate.unavailableAtPercent != null && <p className="match-explanation">Umbral de no disponibilidad del nivel: {candidate.unavailableAtPercent}%.</p>}
        </div>
      </button>
      <div className="candidate-actions"><button className="candidate-detail-link" onClick={onOpen}>Ver detalle <Icon name="arrow" size={15} /></button><button className={`button ${saved ? "button-saved" : "button-outline"}`} onClick={onToggleSave} disabled={busy || disabled}>{busy ? "Guardando..." : saved ? <><Icon name="check" size={16} /> Quitar selección</> : <><Icon name="plus" size={16} /> Seleccionar</>}</button></div>
    </article>
  );
}

function CandidateModal({ candidate, onClose }) {
  if (!candidate) return null;
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="candidate-modal" role="dialog" aria-modal="true" aria-labelledby="candidate-modal-title">
        <button className="icon-button modal-close" onClick={onClose} aria-label="Cerrar"><Icon name="close" /></button>
        <div className="candidate-avatar modal-avatar avatar-lilac">{initialsOf(candidate.name)}<i /></div>
        <p className="eyebrow">Perfil de candidato · {candidate.id}</p>
        <h2 id="candidate-modal-title">{candidate.name}</h2>
        <p className="modal-role">{candidate.role || "Sin rol indicado"} · {candidate.careerLevel || "Nivel no indicado"}</p>
        <div className="detail-grid">
          <div><span>Organization Unit</span><strong>{candidate.organizationUnit || "N/D"}</strong></div>
          <div><span>Talent Segment</span><strong>{candidate.talentSegment || "N/D"}</strong></div>
          <div><span>Localización</span><strong>{candidate.location || "N/D"}</strong></div>
          <div><span>FTE</span><strong>{candidate.resourceFte || "N/D"}</strong></div>
          {"assignedPercent" in candidate && <div><span>Asignado (activo)</span><strong>{formatPercent(candidate.assignedPercent)}</strong></div>}
          {"availablePercent" in candidate && <div><span>Capacidad libre</span><strong>{formatPercent(candidate.availablePercent)}</strong></div>}
          {candidate.industry && <div><span>Industria</span><strong>{candidate.industry}</strong></div>}
        </div>
        <p className="match-explanation">La exportación no incluye habilidades ni currículum: no hay afinidad calculada.</p>
      </section>
    </div>
  );
}

function TalentPage({ onOpenCandidate }) {
  const [people, setPeople] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [location, setLocation] = useState("");
  const [minFree, setMinFree] = useState("");

  useEffect(() => {
    let active = true;
    requestApi("talent/")
      .then((data) => { if (active) setPeople(data.talent); })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, []);

  if (error) return <p className="form-error" role="alert">{error}</p>;
  if (!people) return <p className="api-note" role="status">Cargando...</p>;

  const options = (key) => [...new Set(people.map((person) => person[key]).filter(Boolean))].sort();
  const needle = query.trim().toLowerCase();
  const filtered = people.filter((person) => {
    if (needle && ![person.name, person.id, person.role].some((value) => (value || "").toLowerCase().includes(needle))) return false;
    if (level && person.careerLevel !== level) return false;
    if (location && person.location !== location) return false;
    if (minFree && !(person.availablePercent >= Number(minFree))) return false;
    return true;
  });

  return (
    <section className="talent-page">
      <div className="page-heading"><div><p className="eyebrow">Staff</p><h1>Talento</h1><p>Busca y filtra a las personas del Staff.</p></div></div>
      <div className="talent-filters">
        <label className="field"><span>Buscar</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre, id o rol" /></label>
        <label className="field"><span>Nivel de carrera</span><select value={level} onChange={(event) => setLevel(event.target.value)}><option value="">Todos</option>{options("careerLevel").map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="field"><span>Ubicación</span><select value={location} onChange={(event) => setLocation(event.target.value)}><option value="">Todas</option>{options("location").map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="field"><span>Disponibilidad libre</span><select value={minFree} onChange={(event) => setMinFree(event.target.value)}><option value="">Cualquiera</option><option value="25">≥ 25 %</option><option value="50">≥ 50 %</option><option value="100">≥ 100 %</option></select></label>
      </div>
      <p className="api-note" role="status">{filtered.length} de {people.length} personas</p>
      {filtered.length === 0 ? <p className="api-note">Ninguna persona coincide con la búsqueda.</p> : (
        <table className="mentees-table talent-table">
          <thead><tr><th>Persona</th><th>Rol</th><th>Nivel</th><th>Ubicación</th><th>Ocupación</th><th>Libre</th></tr></thead>
          <tbody>
            {filtered.map((person) => (
              <tr key={person.id} className="clickable-row" tabIndex={0} onClick={() => onOpenCandidate(person)} onKeyDown={(event) => event.key === "Enter" && onOpenCandidate(person)}>
                <td><strong>{person.name}</strong><br /><small>{person.id}</small></td>
                <td>{person.role || "N/D"}</td>
                <td>{person.careerLevel || "N/D"}</td>
                <td>{person.location || "N/D"}</td>
                <td>{formatPercent(person.assignedPercent)} / {formatPercent(person.capacityPercent)}</td>
                <td>{formatPercent(person.availablePercent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function MentorsPage() {
  const [mentors, setMentors] = useState([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    requestApi("mentors/")
      .then((data) => {
        if (!active) return;
        setMentors(data.mentors);
        setSelected(data.mentors[0]?.id ?? "");
      })
      .catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selected) return undefined;
    let active = true;
    setDetail(null);
    requestApi(`mentors/${encodeURIComponent(selected)}/mentees/`)
      .then((data) => active && setDetail(data))
      .catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, [selected]);

  return (
    <section className="mentors-page">
      <label className="field">
        <span>Mentor</span>
        <select value={selected} onChange={(event) => { setError(""); setSelected(event.target.value); }}>
          {mentors.map((mentor) => (
            <option key={mentor.id} value={mentor.id}>
              {mentor.name} ({mentor.menteeCount}){mentor.found ? "" : " · no encontrado en Staff"}{mentor.deleted ? " · dado de baja" : ""}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!detail && !error && <p className="api-note" role="status">Cargando...</p>}
      {detail && (
        <table className="mentees-table">
          <thead><tr><th>Mentorado</th><th>Rol</th><th>Nivel</th><th>Ciudad</th><th>Ocupación</th><th>Asignaciones activas</th></tr></thead>
          <tbody>
            {detail.mentees.map((mentee) => (
              <tr key={mentee.id}>
                <td><strong>{mentee.name}</strong><br /><small>{mentee.id}</small></td>
                <td>{mentee.role || "N/D"}</td>
                <td>{mentee.careerLevel || "N/D"}</td>
                <td>{mentee.location || "N/D"}</td>
                <td>{formatPercent(mentee.assignedPercent)} / {formatPercent(mentee.capacityPercent)}</td>
                <td>{mentee.assignments.length === 0 ? "Sin asignaciones" : mentee.assignments.map((a) => `${a.project || "Sin proyecto"} (${a.assignmentPercent ?? "?"}%)`).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function CompleteDemandModal({ demand, catalog, onClose, onCompleted }) {
  const [form, setForm] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [responsibles, setResponsibles] = useState([]);
  const [chosen, setChosen] = useState(new Set());
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const demandId = demand?.id;

  useEffect(() => {
    if (!demandId) return undefined;
    let active = true;
    requestApi(`demands/${encodeURIComponent(demandId)}/complete/`)
      .then((data) => {
        if (!active) return;
        setForm({ ...data.defaults, assignmentPercent: data.defaults.assignmentPercent ?? "" });
        setCandidates(data.candidates);
        setResponsibles(data.responsibles);
        setChosen(new Set(data.candidates.map((candidate) => candidate.id)));
      })
      .catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, [demandId]);

  if (!demand) return null;

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function toggle(id) {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function submit(event) {
    event.preventDefault();
    if (!form.project.trim() || !form.client.trim() || !form.startingOn || !form.finishingOn) {
      setError("Indica el proyecto, el cliente y las fechas de inicio y fin.");
      return;
    }
    if (form.finishingOn < form.startingOn) {
      setError("La fecha de fin no puede ser anterior a la de inicio.");
      return;
    }
    if (chosen.size === 0) {
      setError("Marca al menos una persona para asignar.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await requestApi(`demands/${encodeURIComponent(demandId)}/complete/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          assignmentPercent: form.assignmentPercent === "" ? null : Number(form.assignmentPercent),
          staffIds: [...chosen],
        }),
      });
      await onCompleted(demandId);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !saving && onClose()}>
      <section className="candidate-modal complete-modal" role="dialog" aria-modal="true" aria-labelledby="complete-modal-title">
        <button className="icon-button modal-close" onClick={onClose} aria-label="Cerrar"><Icon name="close" /></button>
        <p className="eyebrow">Completar demanda · {demand.id}</p>
        <h2 id="complete-modal-title">Asignar a las personas al proyecto</h2>
        <p>Revisa los datos de la asignación. Al confirmar, se registrará en la base de datos, contará para la disponibilidad de cada persona y la demanda pasará a «Cubierta».</p>
        {!form && !error && <p className="api-note" role="status">Cargando...</p>}
        {form && (
          <form onSubmit={submit}>
            <h3>Personas asignadas</h3>
            {candidates.length === 0 ? <p className="api-note">Esta demanda no tiene candidatos seleccionados. Vuelve a la búsqueda y pulsa «Seleccionar» en alguno.</p> : (
              <ul className="complete-candidates">
                {candidates.map((candidate) => (
                  <li key={candidate.id}>
                    <label><input type="checkbox" checked={chosen.has(candidate.id)} onChange={() => toggle(candidate.id)} /> <span><strong>{candidate.name}</strong> · {candidate.role || "Sin rol"}</span></label>
                    <small>Libre en la fecha de inicio: {formatPercent(candidate.availablePercent)}</small>
                  </li>
                ))}
              </ul>
            )}
            <h3>Datos de la asignación</h3>
            <div className="form-grid">
              <label className="field field-full"><span>Proyecto <b>*</b></span><input value={form.project} onChange={(e) => update("project", e.target.value)} /></label>
              <label className="field"><span>Cliente <b>*</b></span><input value={form.client} onChange={(e) => update("client", e.target.value)} placeholder="Ej. BBVA" /></label>
              <label className="field"><span>Industria</span><select value={form.industry} onChange={(e) => update("industry", e.target.value)}><option value="">Sin especificar</option>{catalog.industries.map((industry) => <option key={industry}>{industry}</option>)}</select></label>
              <label className="field"><span>Fecha de inicio <b>*</b></span><input type="date" value={form.startingOn} onChange={(e) => update("startingOn", e.target.value)} /></label>
              <label className="field"><span>Fecha de fin <b>*</b></span><input type="date" value={form.finishingOn} onChange={(e) => update("finishingOn", e.target.value)} /></label>
              <label className="field"><span>% de dedicación</span><input type="number" min="1" max="100" value={form.assignmentPercent} onChange={(e) => update("assignmentPercent", e.target.value)} placeholder="Ej. 50" /><small>Si lo dejas vacío se usa toda la capacidad libre de cada persona.</small></label>
              <label className="field"><span>Responsable</span><select value={form.responsible} onChange={(e) => update("responsible", e.target.value)}><option value="">Sin especificar</option>{responsibles.map((person) => <option key={person.id} value={person.id}>{person.name} ({person.id})</option>)}</select><small>Persona que lidera el proyecto.</small></label>
              <label className="field"><span>Vendido</span><input type="checkbox" checked={!!form.sold} onChange={(e) => update("sold", e.target.checked)} /></label>
              <label className="field"><span>Fin confirmado</span><input type="checkbox" checked={!!form.confirmedEnd} onChange={(e) => update("confirmedEnd", e.target.checked)} /></label>
              <label className="field field-full"><span>Comentarios</span><textarea rows="3" value={form.comments} onChange={(e) => update("comments", e.target.value)} /></label>
            </div>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="form-footer"><p><b>*</b> Obligatorio</p><div><button className="button button-quiet" type="button" onClick={onClose} disabled={saving}>Cancelar</button><button className="button button-purple" type="submit" disabled={saving || candidates.length === 0}>{saving ? "Asignando..." : "Confirmar asignación"}</button></div></div>
          </form>
        )}
        {!form && error && <p className="form-error" role="alert">{error}</p>}
      </section>
    </div>
  );
}

const DEMAND_STATUSES = ["Nueva", "Búsqueda en curso", "En revisión", "Cubierta", "Cancelada"];

function DemandDetail({ demand, onClose, onSearch, onStatusChange, onDelete, onEdit, onComplete }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!demand) return null;

  async function run(action) {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="candidate-modal demand-modal" role="dialog" aria-modal="true" aria-labelledby="demand-modal-title">
        <button className="icon-button modal-close" onClick={onClose} aria-label="Cerrar"><Icon name="close" /></button>
        <p className="eyebrow">Detalle de demanda · {demand.id}</p>
        <h2 id="demand-modal-title">{demand.title}</h2>
        <label className="field"><span>Estado</span><select value={demand.status} disabled={busy} onChange={(event) => run(() => onStatusChange(demand.id, event.target.value))}>{DEMAND_STATUSES.filter((status) => status !== "Cubierta" || demand.status === "Cubierta").map((status) => <option key={status}>{status}</option>)}</select><small>«Cubierta» se asigna al completar la demanda.</small></label>
        <div className="detail-grid"><div><span>Rol</span><strong>{demand.role}</strong></div><div><span>Seniority</span><strong>{demand.seniority}</strong></div><div><span>Industria</span><strong>{demand.industry || "Sin especificar"}</strong></div><div><span>Offering</span><strong>{demand.offering || "Sin especificar"}</strong></div><div><span>Disponibilidad</span><strong>{demand.availability || "Flexible"}</strong></div><div><span>Ocupación</span><strong>{demand.occupancy || "Sin especificar"}</strong></div><div><span>Localización</span><strong>{demand.location} · {demand.modality}</strong></div><div><span>Inicio</span><strong>{formatDate(demand.startDate)}</strong></div><div><span>Duración</span><strong>{demand.duration}</strong></div></div>
        <h3>Habilidades clave</h3><div className="skill-list modal-skills">{demand.skills.map((skill) => <span key={skill}>{skill}</span>)}</div>
        {demand.description && <><h3>Descripción</h3><p>{demand.description}</p></>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-purple modal-action" onClick={onSearch}>Ver y seleccionar candidatos <Icon name="arrow" size={16} /></button>
        <button className="button button-outline modal-action" disabled={busy} onClick={() => onEdit(demand)}>Editar demanda</button>
        {!/cubierta|cancelada/i.test(demand.status) && <button className="button button-purple modal-action" disabled={busy} onClick={() => onComplete(demand)}>Completar demanda</button>}
        <button className="button button-outline modal-action" disabled={busy} onClick={() => window.confirm("¿Eliminar la demanda y sus candidatos seleccionados?") && run(() => onDelete(demand.id))}>Eliminar demanda</button>
      </section>
    </div>
  );
}

function Workspace() {
  const [page, setPage] = useState("home");
  const [demands, setDemands] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [activeDemand, setActiveDemand] = useState(null);
  const [detailDemand, setDetailDemand] = useState(null);
  const [detailCandidate, setDetailCandidate] = useState(null);
  const [editingDemand, setEditingDemand] = useState(null);
  const [completing, setCompleting] = useState(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([requestApi("demands/"), requestApi("candidates/"), requestApi("catalog/")])
      .then(([demandData, candidateData, catalogData]) => {
        if (!active) return;
        setDemands(demandData.demands);
        setActiveDemand(demandData.demands[0] ?? null);
        setCandidates(candidateData.candidates);
        setCatalog(catalogData);
      })
      .catch((error) => {
        if (active) setLoadError(error.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [reloadKey]);

  async function createDemand(demand) {
    const savedDemand = await requestApi("demands/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(demand),
    });
    setDemands((current) => [savedDemand, ...current]);
    setActiveDemand(savedDemand);
    setPage("results");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveDemand(changes) {
    const updated = await requestApi(`demands/${encodeURIComponent(editingDemand.id)}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    const replace = (current) => (current && current.id === updated.id ? updated : current);
    setDemands((current) => current.map((demand) => replace(demand)));
    setActiveDemand(replace);
    setDetailDemand(null);
    setEditingDemand(null);
    setPage("demands");
  }

  async function finishCompletion(id) {
    await refreshDemand(id);
    setCompleting(null);
  }

  function startEdit(demand) {
    setDetailDemand(null);
    setEditingDemand(demand);
    setPage("edit");
  }

  function openDemand(demand) {
    setDetailDemand(demand);
  }

  function goToResults(demand = activeDemand) {
    if (!demand) return;
    setActiveDemand(demand);
    setDetailDemand(null);
    setPage("results");
  }

  async function refreshDemand(id) {
    const refreshed = await requestApi(`demands/${encodeURIComponent(id)}/`);
    const replace = (current) => (current && current.id === id ? refreshed : current);
    setDemands((current) => current.map((demand) => replace(demand)));
    setActiveDemand(replace);
    setDetailDemand(replace);
  }

  async function updateDemandStatus(id, status) {
    const updated = await requestApi(`demands/${encodeURIComponent(id)}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const replace = (current) => (current && current.id === id ? updated : current);
    setDemands((current) => current.map((demand) => replace(demand)));
    setActiveDemand(replace);
    setDetailDemand(replace);
  }

  async function deleteDemand(id) {
    await requestApi(`demands/${encodeURIComponent(id)}/`, { method: "DELETE" });
    setDemands((current) => current.filter((demand) => demand.id !== id));
    setActiveDemand((current) => (current?.id === id ? null : current));
    setDetailDemand(null);
  }

  function reloadData() {
    setLoading(true);
    setLoadError("");
    setReloadKey((key) => key + 1);
  }

  const pageTitle = page === "home" ? "Inicio" : page === "demands" ? "Demandas" : page === "talent" ? "Talento" : page === "results" ? "Candidatos" : page === "mentors" ? "Mentores" : page === "edit" ? "Editar demanda" : "Crear demanda";

  if (loading) {
    return <main className="api-state"><p>Cargando datos...</p></main>;
  }

  if (loadError) {
    return (
      <main className="api-state" role="alert">
        <h1>No se pudieron cargar los datos</h1>
        <p>{loadError}</p>
        <button className="button button-purple" onClick={reloadData}>Reintentar</button>
      </main>
    );
  }

  return (
    <div className="workspace">
      <Sidebar
        page={page}
        setPage={(nextPage) => { setPage(nextPage); setMobileNavOpen(false); }}
        demandCount={demands.length}
      />
      {mobileNavOpen && <button className="mobile-nav-backdrop" aria-label="Cerrar menú" onClick={() => setMobileNavOpen(false)} />}
      <div className="workspace-main">
        <Topbar title={pageTitle} onNewDemand={() => setPage("create")} />
        <button className="mobile-menu-button" onClick={() => setMobileNavOpen((open) => !open)} aria-label="Abrir menú"><span /><span /><span /></button>
        <main className="page-content">
          {page === "home" && <Dashboard demands={demands} candidates={candidates} setPage={setPage} onNewDemand={() => setPage("create")} onOpenDemand={openDemand} />}
          {page === "demands" && (
            <div className="demands-page">
              <div className="page-heading"><div><p className="eyebrow">Tu pipeline de talento</p><h1>Demandas</h1><p>Haz seguimiento de las búsquedas y encuentra el talento adecuado.</p></div><button className="button button-purple" onClick={() => setPage("create")}><Icon name="plus" size={17} /> Nueva demanda</button></div>
              <div className="demand-summary-row"><div><span className="summary-number">{demands.length}</span><span>Demandas registradas</span></div><div><span className="summary-number">{candidates.length}</span><span>Candidatos disponibles</span></div><div><span className="summary-number">{demands.filter((demand) => /cubierta|covered/i.test(demand.status)).length}</span><span>Demandas cubiertas</span></div></div>
              <div className="list-heading"><h2>Todas las demandas <span>{demands.length}</span></h2><button className="filter-button"><Icon name="filter" size={17} /> Filtrar</button></div>
              <DemandTable demands={demands} onOpenDemand={openDemand} />
            </div>
          )}
          {page === "create" && <DemandForm catalog={catalog} onCancel={() => setPage("demands")} onSubmit={createDemand} />}
          {page === "edit" && editingDemand && <DemandForm key={editingDemand.id} demand={editingDemand} catalog={catalog} onCancel={() => { setEditingDemand(null); setPage("demands"); }} onSubmit={saveDemand} />}
          {page === "talent" && <TalentPage onOpenCandidate={setDetailCandidate} />}
          {page === "mentors" && <MentorsPage />}
          {page === "results" && <ResultsPage demand={activeDemand} onBack={() => setPage("demands")} onOpenCandidate={setDetailCandidate} onDemandChanged={refreshDemand} onComplete={setCompleting} />}
        </main>
      </div>
      <CandidateModal candidate={detailCandidate} onClose={() => setDetailCandidate(null)} />
      <DemandDetail key={detailDemand?.id} demand={detailDemand} onClose={() => setDetailDemand(null)} onSearch={() => goToResults(detailDemand)} onStatusChange={updateDemandStatus} onDelete={deleteDemand} onEdit={startEdit} onComplete={(demand) => { setDetailDemand(null); setCompleting(demand); }} />
      <CompleteDemandModal key={completing?.id} demand={completing} catalog={catalog} onClose={() => setCompleting(null)} onCompleted={finishCompletion} />
    </div>
  );
}

export default function App() {
  return <Workspace />;
}

function formatDate(value) {
  if (!value) return "Por definir";
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric" }).format(date);
}
