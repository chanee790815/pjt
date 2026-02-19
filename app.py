' =======================================================================
' 1. [통합 대시보드] 생성 매크로 (모든 현장 요약) - 웹 메인페이지 클론
' =======================================================================
Sub CreateMainDashboard()
    Dim wsDash As Worksheet
    Dim wb As Workbook
    Dim ws As Worksheet
    Dim rowPos As Integer, colPos As Integer
    Dim pjtCount As Integer
    Dim avgProg As Double
    Dim lastRow As Long
    
    Set wb = ThisWorkbook
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    
    ' 기존 통합 대시보드 삭제 후 재생성 (이모지 제거)
    On Error Resume Next
    wb.Sheets("통합 대시보드").Delete
    On Error GoTo 0
    
    Set wsDash = wb.Sheets.Add(Before:=wb.Sheets(1))
    wsDash.Name = "통합 대시보드"
    ActiveWindow.DisplayGridlines = False
    wsDash.Cells.Interior.Color = RGB(255, 255, 255) ' 전체 배경 흰색
    
    ' --- 타이틀 ---
    wsDash.Range("B2").Value = "통합 대시보드"
    wsDash.Range("B2").Font.Size = 24
    wsDash.Range("B2").Font.Bold = True
    
    ' --- 활성 프로젝트 개수 카운트 ---
    pjtCount = 0
    For Each ws In wb.Sheets
        If Not IsSystemSheet(ws.Name) Then pjtCount = pjtCount + 1
    Next ws
    
    ' --- 요약 바 ---
    wsDash.Range("B4:J4").Merge
    wsDash.Range("B4").Value = "  현재 관리 중인 현장: " & pjtCount & "개"
    wsDash.Range("B4").Interior.Color = RGB(232, 244, 254) ' 연한 파란색 배경
    wsDash.Range("B4").Font.Color = RGB(25, 103, 210)
    wsDash.Range("B4").Font.Bold = True
    wsDash.Range("B4").VerticalAlignment = xlCenter
    wsDash.Range("B4").RowHeight = 35
    
    ' --- 카드 레이아웃 그리기 ---
    rowPos = 6
    colPos = 2 ' B열 시작
    Dim cardIdx As Integer: cardIdx = 0
    
    For Each ws In wb.Sheets
        If Not IsSystemSheet(ws.Name) Then
            cardIdx = cardIdx + 1
            
            ' 진척률 계산 (G열)
            lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
            If lastRow >= 2 Then
                On Error Resume Next
                avgProg = Application.WorksheetFunction.Average(ws.Range("G2:G" & lastRow))
                If Err.Number <> 0 Then avgProg = 0
                On Error GoTo 0
            Else
                avgProg = 0
            End If
            
            ' 1) 카드 테두리 및 배경
            With wsDash.Range(wsDash.Cells(rowPos, colPos), wsDash.Cells(rowPos + 5, colPos + 3))
                .Borders.LineStyle = xlContinuous
                .Borders.Color = RGB(220, 220, 220)
                .Interior.Color = RGB(255, 255, 255)
            End With
            
            ' 2) 현장 이름 (Title) - 이모지 제거 후 텍스트 대체
            wsDash.Cells(rowPos + 1, colPos + 1).Value = "[현장] " & ws.Name
            wsDash.Cells(rowPos + 1, colPos + 1).Font.Size = 14
            wsDash.Cells(rowPos + 1, colPos + 1).Font.Bold = True
            
            ' 3) 상태 텍스트 (Subtitle)
            wsDash.Cells(rowPos + 2, colPos + 1).Value = "업데이트 완료"
            wsDash.Cells(rowPos + 2, colPos + 1).Font.Color = RGB(150, 150, 150)
            wsDash.Cells(rowPos + 2, colPos + 1).Font.Size = 10
            
            ' 4) 진척률 텍스트
            wsDash.Cells(rowPos + 4, colPos + 1).Value = "진척률: " & Format(avgProg, "0.0") & "%"
            wsDash.Cells(rowPos + 4, colPos + 1).Font.Size = 10
            
            ' 5) 웹 스타일 프로그레스 바 (Shape 객체로 HTML Bar 완벽 구현)
            Dim barRng As Range
            Set barRng = wsDash.Range(wsDash.Cells(rowPos + 5, colPos + 1), wsDash.Cells(rowPos + 5, colPos + 2))
            
            ' 회색 바탕 바
            Dim shpBg As Shape
            Set shpBg = wsDash.Shapes.AddShape(msoShapeRectangle, barRng.Left, barRng.Top - 5, barRng.Width, 6)
            shpBg.Line.Visible = msoFalse
            shpBg.Fill.ForeColor.RGB = RGB(230, 240, 255)
            
            ' 파란색 진행 바
            If avgProg > 0 Then
                Dim shpFill As Shape
                Set shpFill = wsDash.Shapes.AddShape(msoShapeRectangle, barRng.Left, barRng.Top - 5, barRng.Width * (avgProg / 100), 6)
                shpFill.Line.Visible = msoFalse
                shpFill.Fill.ForeColor.RGB = RGB(25, 103, 210) ' Streamlit Primary Blue
            End If
            
            ' 레이아웃 2단 배치 계산 (좌/우)
            If cardIdx Mod 2 = 1 Then
                colPos = 7 ' 오른쪽 열로 이동 (G열)
            Else
                colPos = 2 ' 왼쪽 열로 복귀 (B열)
                rowPos = rowPos + 7 ' 아래로 한 칸 이동
            End If
        End If
    Next ws
    
    ' --- 열 너비 정리 ---
    wsDash.Columns("A").ColumnWidth = 3
    wsDash.Columns("B").ColumnWidth = 2
    wsDash.Columns("C:D").ColumnWidth = 18
    wsDash.Columns("E").ColumnWidth = 2
    wsDash.Columns("F").ColumnWidth = 3 ' 중앙 여백
    wsDash.Columns("G").ColumnWidth = 2
    wsDash.Columns("H:I").ColumnWidth = 18
    wsDash.Columns("J").ColumnWidth = 2
    
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    MsgBox "통합 대시보드 생성이 완료되었습니다!", vbInformation, "메인페이지 생성"
End Sub

' =======================================================================
' 2. [개별 현장 간트차트] 생성 매크로 - 웹 프로젝트 상세 클론
' =======================================================================
Sub CreateProjectGantt()
    Dim wsData As Worksheet, wsGantt As Worksheet
    Dim wb As Workbook
    Dim lastRow As Long, r As Long, c As Long
    Set wb = ThisWorkbook
    
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    Set wsData = ActiveSheet
    
    ' 시스템 시트 실행 방지
    If IsSystemSheet(wsData.Name) Then
        MsgBox "데이터가 있는 개별 현장 시트(예: 기아 광명공장)를 선택한 후 실행해주세요.", vbExclamation, "시트 선택 오류"
        Exit Sub
    End If
    If wsData.Range("A1").Value <> "시작일" Then
        MsgBox "[시작일, 종료일, 대분류...] 형식의 데이터 시트가 아닙니다.", vbCritical, "양식 오류"
        Exit Sub
    End If
    
    On Error Resume Next
    wb.Sheets("프로젝트 간트차트").Delete
    On Error GoTo 0
    
    lastRow = wsData.Cells(wsData.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then
        MsgBox "입력된 데이터가 없습니다.", vbExclamation, "데이터 없음"
        Exit Sub
    End If
    
    Set wsGantt = wb.Sheets.Add(After:=wsData)
    wsGantt.Name = "프로젝트 간트차트"
    ActiveWindow.DisplayGridlines = False
    wsGantt.Cells.Interior.Color = RGB(255, 255, 255)
    
    wsGantt.Range("B2").Value = "[" & wsData.Name & "] 상세 간트차트"
    wsGantt.Range("B2").Font.Size = 18
    wsGantt.Range("B2").Font.Bold = True
    
    wsGantt.Range("B4:F4").Value = Array("대분류", "구분", "시작일", "종료일", "진행률(%)")
    wsGantt.Range("B4:F4").Interior.Color = RGB(240, 242, 246)
    wsGantt.Range("B4:F4").Font.Bold = True
    wsGantt.Range("B4:F4").HorizontalAlignment = xlCenter
    
    For r = 2 To lastRow
        wsGantt.Cells(r + 3, 2).Value = wsData.Cells(r, 3).Value
        wsGantt.Cells(r + 3, 3).Value = wsData.Cells(r, 4).Value
        wsGantt.Cells(r + 3, 4).Value = wsData.Cells(r, 1).Value
        wsGantt.Cells(r + 3, 5).Value = wsData.Cells(r, 2).Value
        wsGantt.Cells(r + 3, 6).Value = wsData.Cells(r, 7).Value
    Next r
    
    wsGantt.Columns("D:E").NumberFormat = "yyyy-mm-dd"
    wsGantt.Columns("B").ColumnWidth = 14
    wsGantt.Columns("C").ColumnWidth = 28
    wsGantt.Columns("D:E").ColumnWidth = 12
    wsGantt.Columns("F").ColumnWidth = 10
    
    Dim minDate As Date, maxDate As Date
    minDate = Application.WorksheetFunction.Min(wsData.Range("A2:A" & lastRow))
    maxDate = Application.WorksheetFunction.Max(wsData.Range("B2:B" & lastRow))
    
    If minDate = 0 Then minDate = Date
    If maxDate = 0 Then maxDate = Date + 30
    minDate = minDate - Weekday(minDate, vbMonday) + 1
    
    Dim currDate As Date: currDate = minDate
    Dim tCol As Integer: tCol = 7
    
    Do While currDate <= maxDate + 14
        wsGantt.Cells(4, tCol).Value = currDate
        wsGantt.Cells(4, tCol).NumberFormat = "mm/dd"
        wsGantt.Cells(4, tCol).Font.Size = 8
        wsGantt.Cells(4, tCol).Orientation = xlUpward
        wsGantt.Columns(tCol).ColumnWidth = 2.5
        currDate = currDate + 7
        tCol = tCol + 1
    Loop
    
    wsGantt.Range(wsGantt.Cells(4, 7), wsGantt.Cells(4, tCol - 1)).Interior.Color = RGB(240, 242, 246)
    
    Dim tStart As Date, tEnd As Date, Prog As Double, wStart As Date, wEnd As Date
    For r = 5 To lastRow + 3
        If IsDate(wsGantt.Cells(r, 4).Value) And IsDate(wsGantt.Cells(r, 5).Value) Then
            tStart = wsGantt.Cells(r, 4).Value
            tEnd = wsGantt.Cells(r, 5).Value
            Prog = Val(wsGantt.Cells(r, 6).Value)
            
            For c = 7 To tCol - 1
                wStart = wsGantt.Cells(4, c).Value
                wEnd = wStart + 6
                If tStart <= wEnd And tEnd >= wStart Then
                    wsGantt.Cells(r, c).Interior.Color = GetPlotlyColor(Prog)
                End If
            Next c
        End If
    Next r
    
    wsGantt.Range("B4:F" & lastRow + 3).Borders.LineStyle = xlContinuous
    wsGantt.Range("B5:B" & lastRow + 3).HorizontalAlignment = xlCenter
    wsGantt.Range("D5:F" & lastRow + 3).HorizontalAlignment = xlCenter
    
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    MsgBox "[" & wsData.Name & "] 현장 간트차트 생성이 완료되었습니다!", vbInformation, "상세페이지 생성"
End Sub

' --- 시스템 시트 여부 확인 함수 ---
Function IsSystemSheet(sheetName As String) As Boolean
    Dim sysSheets As Variant
    ' 이모지를 모두 제거하고 정확한 텍스트로 수정
    sysSheets = Array("통합 대시보드", "프로젝트 간트차트", "DB_업로드양식", "프로젝트_데이터", "KPI", "Solar_DB", "weekly_history")
    Dim i As Integer
    IsSystemSheet = False
    For i = LBound(sysSheets) To UBound(sysSheets)
        If sheetName = sysSheets(i) Then
            IsSystemSheet = True
            Exit Function
        End If
    Next i
End Function

' --- 간트차트 색상 (Plotly RdYlGn) ---
Function GetPlotlyColor(prog As Double) As Long
    If prog = 0 Then
        GetPlotlyColor = RGB(178, 24, 43)    ' 0%
    ElseIf prog < 20 Then
        GetPlotlyColor = RGB(214, 96, 77)    ' 1~19%
    ElseIf prog < 40 Then
        GetPlotlyColor = RGB(244, 165, 130)  ' 20~39%
    ElseIf prog < 60 Then
        GetPlotlyColor = RGB(253, 219, 199)  ' 40~59%
    ElseIf prog < 80 Then
        GetPlotlyColor = RGB(209, 229, 240)  ' 60~79%
    ElseIf prog < 100 Then
        GetPlotlyColor = RGB(146, 197, 222)  ' 80~99%
    Else
        GetPlotlyColor = RGB(26, 152, 80)    ' 100%
    End If
End Function
