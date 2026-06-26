import { PublishArtifact } from "@/lib/api";

export function PublishCards({ artifact }: { artifact: PublishArtifact }) {
  const { confluence_doc, jira_ticket } = artifact;
  return (
    <div className="cards">
      <div className="card">
        <div className="card-head">Confluence doc · {confluence_doc.id}</div>
        <div className="card-body">
          <h4>{confluence_doc.title}</h4>
          <span className="tag">{confluence_doc.category}</span>
          {confluence_doc.description && (
            <p className="muted" style={{ fontSize: 13.5, marginTop: 8 }}>
              {confluence_doc.description}
            </p>
          )}
          {confluence_doc.properties.length > 0 && (
            <table className="prop-table mt-12">
              <thead>
                <tr>
                  <th>Property</th>
                  <th>Type</th>
                  <th>Required</th>
                </tr>
              </thead>
              <tbody>
                {confluence_doc.properties.map((p) => (
                  <tr key={p.name}>
                    <td>{p.name}</td>
                    <td>{p.type}</td>
                    <td>{p.required ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-head">Jira ticket</div>
        <div className="card-body">
          <div className="ticket-key">{jira_ticket.key}</div>
          <h4 style={{ marginTop: 4 }}>{jira_ticket.summary}</h4>
          <pre
            className="mono muted"
            style={{ fontSize: 12.5, whiteSpace: "pre-wrap", margin: "8px 0 0" }}
          >
            {jira_ticket.body}
          </pre>
        </div>
      </div>
    </div>
  );
}
