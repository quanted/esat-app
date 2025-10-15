

def create_optimized_plotly_html(fig, xanchor='center', x: float = None, static_plot: bool = False) -> str:
    """Create optimized HTML for faster rendering."""
    # Optimize figure for performance
    fig.update_layout(
        title=dict(font=dict(size=16), x=x, xanchor=xanchor),
        width=None,
        height=None,
        autosize=True,
        # Reduce animation duration or disable
        transition_duration=0,
        # Optimize rendering
        uirevision=True,  # Prevents unnecessary re-rendering
        margin=dict(l=20, r=20, t=80, b=20),
        scene=dict(
            camera=dict(projection=dict(type="orthographic"))
        )
    )

    # Generate HTML with performance optimizations
    html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',  # You're already doing this
        config={
            'responsive': True,
            'displayModeBar': True,
            # Performance optimizations
            'staticPlot': static_plot,  # Set to True if no interactivity needed
            'displaylogo': False,
            'modeBarButtonsToRemove': [
                'pan2d', 'lasso2d', 'select2d', 'autoScale2d',
                'hoverClosestCartesian', 'hoverCompareCartesian'
            ],
            # Reduce memory usage
            'scrollZoom': True,
            'doubleClick': 'reset'
        }
    )
    return html