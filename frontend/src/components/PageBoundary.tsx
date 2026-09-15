import { Component, type ReactNode } from "react";

export default class PageBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() { return { failed: true }; }

  render() {
    if (this.state.failed) {
      return <main className="core-shell" role="alert">
        <h1>Page unavailable</h1>
        <p>This page could not display its data. You can still use the navigation above.</p>
        <button type="button" onClick={() => this.setState({ failed: false })}>TRY AGAIN</button>
      </main>;
    }
    return this.props.children;
  }
}
