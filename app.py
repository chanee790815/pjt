with t3:
            # 1. 주간 주요 현황 업데이트 (메인 대시보드 브리핑용)
            st.subheader("📢 주간 주요 현황 업데이트")
            curr_note = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            with st.form("up_f"):
                new_t = st.text_input("이번 주 주요 이슈 (메인 장표 노출)", value=curr_note)
                if st.form_submit_button("주간 현황 반영"):
                    # 시트의 F2 셀(비고) 업데이트
                    target_ws.update_acell("F2", new_t)
                    st.success("대시보드에 반영되었습니다."); time.sleep(1); st.rerun()
            
            st.divider()

            # 2. 개별 공정 현황 수정
            st.subheader("🛠️ 개별 공정 현황 수정")
            if not df_raw.empty:
                # 수정을 위한 공정 선택 리스트 생성
                df_raw['select_name'] = df_raw['구분'] + " (" + df_raw['시작일'].astype(str) + ")"
                target_task = st.selectbox("수정할 공정을 선택하세요", df_raw['select_name'].tolist())
                
                # 선택한 공정의 데이터 추출
                idx = df_raw[df_raw['select_name'] == target_task].index[0]
                row_data = df_raw.iloc[idx]
                
                with st.form("edit_task_form"):
                    col1, col2 = st.columns(2)
                    # 진행상태 및 진행률 수정
                    new_stat = col1.selectbox("진행상태", ["예정", "진행중", "완료", "지연"], 
                                           index=["예정", "진행중", "완료", "지연"].index(row_data['진행상태']))
                    new_pct = col2.number_input("진행률(%)", 0, 100, int(row_data['진행률']))
                    new_memo = st.text_area("공정별 세부 비고", value=row_data['비고'])
                    
                    if st.form_submit_button("공정 정보 업데이트"):
                        # 구글 시트의 해당 행(E, F, G열) 업데이트
                        target_ws.update(f"E{idx+2}:G{idx+2}", [[new_stat, new_memo, new_pct]])
                        st.success(f"'{row_data['구분']}' 공정이 업데이트되었습니다."); time.sleep(1); st.rerun()
            else:
                st.info("수정할 데이터가 없습니다.")

            st.divider()
            
            # 3. 프로젝트 설정 관리 (이름 변경 및 삭제)
            st.subheader("⚙️ 프로젝트 설정 관리")
            col_left, col_right = st.columns(2)
            
            with col_left:
                new_name = st.text_input("프로젝트 명칭 변경", value=selected)
                if st.button("명칭 수정 적용"):
                    if new_name != selected:
                        target_ws.update_title(new_name)
                        st.success("이름이 변경되었습니다."); time.sleep(1); st.rerun()
            
            with col_right:
                if st.button("🗑️ 이 프로젝트 전체 삭제", type="primary"):
                    if len(all_ws) > 1:
                        sh.del_worksheet(target_ws)
                        st.warning("프로젝트가 삭제되었습니다."); time.sleep(1); st.rerun()
                    else:
                        st.error("마지막 남은 프로젝트는 삭제할 수 없습니다.")
