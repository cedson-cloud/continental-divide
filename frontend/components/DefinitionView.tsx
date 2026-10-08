import { EventDefinition } from "@/lib/api";
import { definitionTitle } from "@/lib/format";

export function DefinitionView({ definition }: { definition: EventDefinition }) {
  const isTrack = (definition.call_type ?? "track") === "track";
  const fields = isTrack ? definition.properties : (definition.traits ?? []);
  const fieldLabel = isTrack ? "Property" : "Trait";
  return (
    <div>
      <div className="row spread">
        <h3 style={{ margin: 0, fontSize: 17 }}>{definitionTitle(definition)}</h3>
        <span className="tag">
          {isTrack ? definition.category : definition.call_type}
        </span>
      </div>
      {definition.description && (
        <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
          {definition.description}
        </p>
      )}
      {fields.length > 0 ? (
        <table className="prop-table mt-12">
          <thead>
            <tr>
              <th>{fieldLabel}</th>
              <th>Type</th>
              <th>Required</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((prop) => (
              <tr key={prop.name}>
                <td>{prop.name}</td>
                <td>{prop.type}</td>
                <td>{prop.required ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted mt-12" style={{ fontSize: 13.5 }}>
          {isTrack ? "No properties defined." : "No traits defined."}
        </p>
      )}
    </div>
  );
}
