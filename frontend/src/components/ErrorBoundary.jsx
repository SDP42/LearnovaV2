import { Component } from "react";

/**
 * Catches render-time errors anywhere below it so one broken page shows a
 * recoverable message instead of a blank white screen.
 */
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Learnova UI error:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-4 p-8 text-center">
        <h1 className="text-lg font-semibold">Something broke on this page</h1>
        <p className="text-sm text-muted-foreground">
          {String(this.state.error?.message || this.state.error)}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => this.setState({ error: null })}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Try again
          </button>
          <a
            href="/app"
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          >
            Back to dashboard
          </a>
        </div>
      </div>
    );
  }
}
