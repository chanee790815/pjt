# [탭 1] 공정표 조회 부분의 핵심 로직입니다. 이 부분 위주로 확인해 주세요.

with tab1:
    st.subheader("실시간 공정 현황")
    if not df_raw.empty:
        try:
            df = df_raw.copy()
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            df['구분'] = df['구분'].astype(str).str.strip()
            
            # 1. [핵심] 시작일 기준으로 데이터를 정렬합니다. 
            # 이제 업무를 새로 추가해도 '시작일'만 맞으면 자동으로 순서가 배치됩니다.
            df = df.sort_values(by="시작일", ascending=True).reset_index(drop=True)

            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()
            
            # 2. [가장 중요] 현재 정렬된 '구분' 리스트를 뽑아냅니다.
            # Plotly에게 "이 리스트에 있는 순서대로 위에서 아래로 그려줘"라고 명령하는 리스트입니다.
            y_axis_order = main_df['구분'].unique().tolist()

            # 3. 간트 차트 생성
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                hover_data=["대분류", "비고"],
                # category_orders에 정렬된 리스트를 주입하여 순서를 강제합니다.
                category_orders={"구분": y_axis_order}
            )

            # 4. 레이아웃 설정
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(
                    side="top", 
                    showgrid=True, 
                    gridcolor="rgba(220, 220, 220, 0.8)", 
                    dtick="M1", 
                    tickformat="%Y-%m", 
                    ticks="outside"
                ),
                yaxis=dict(
                    # autorange를 "reversed"로 설정해야 리스트의 첫 번째(가장 빠른 날짜)가 맨 위로 옵니다.
                    autorange="reversed", 
                    showgrid=True, 
                    gridcolor="rgba(240, 240, 240, 0.8)",
                    title="공정명"
                ),
                height=800,
                margin=dict(t=150, l=10, r=10, b=50),
                showlegend=True
            )
            
            fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.8)
            st.plotly_chart(fig, use_container_width=True)
