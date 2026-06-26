import { EventDefinition } from "@/lib/api";

export function DefinitionView({ definition }: { definition: EventDefinition }) {
  return (
    <div>
      <div className="row spread">
        <h3 style={{ margin: 0, fontSize: 17 }}>{definition.name}</h3>
        <span className="tag">{definition.category}</span>
      </div>
      {definition.description && (
        <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
          {definition.description}
        </p>
      )}
      {definition.properties.length > 0 ? (
        <table className="prop-table mt-12">
          <thead>
            <tr>
              <th>Property</th>
              <th>Type</th>
              <th>Required</th>
            </tr>
          </thead>
          <tbody>
            {definition.properties.map((prop) => (
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
          No properties defined.
        </p>
      )}
    </div>
  );
}
